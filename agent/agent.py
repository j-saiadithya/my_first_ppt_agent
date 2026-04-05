"""
Auto-PPT Agent — Steps 4, 5, 6
================================
The AI Agent that:
  1. PLANS a presentation (Step 5)
  2. EXECUTES the plan via MCP tool calls (Step 6)
  3. OBSERVES each result before proceeding (Step 6)

Architecture:
  User Prompt --> plan() --> execute() --> .pptx file

The agent uses HuggingFace's Inference API for LLM reasoning
and the MCP Client to call PPT tools on the MCP server.
"""

import sys
import os
import json
import re
import asyncio

# Fix Windows console encoding
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from huggingface_hub import InferenceClient
from agent.config import HF_API_KEY
from agent.mcp_client import MCPClient


# ──────────────────────────────────────────────────────────────────────────────
# System prompts for the LLM
# ──────────────────────────────────────────────────────────────────────────────

PLANNING_PROMPT = """You are a presentation planning assistant.

Given a user's topic, create a structured plan for a PowerPoint presentation.

RULES:
- The presentation must have a title and {num_slides} content slides.
- Each slide must have a clear title (3-7 words).
- Each slide must have exactly 3 to 5 bullet points.
- Each bullet point must be 12 words or fewer.
- Do NOT write paragraphs. Only short bullet points.
- Bullets should be informative and specific, not vague.

You MUST respond with ONLY valid JSON in this exact format (no extra text):
{{
  "presentation_title": "The Main Title of the Presentation",
  "slides": [
    {{
      "title": "Slide Title Here",
      "bullets": [
        "First bullet point here",
        "Second bullet point here",
        "Third bullet point here"
      ]
    }}
  ]
}}

Respond with ONLY the JSON. No markdown, no explanation, no code fences."""

CONTENT_ENHANCEMENT_PROMPT = """You are helping create presentation content.

Topic: {topic}
Slide Title: {slide_title}

Generate exactly {num_bullets} bullet points for this slide.

RULES:
- Each bullet must be 12 words or fewer
- Be specific and informative
- No paragraphs, only short bullet points

Respond with ONLY a JSON array of strings:
["bullet 1", "bullet 2", "bullet 3"]

No extra text. Only the JSON array."""

RESEARCH_ENHANCEMENT_PROMPT = """You are enhancing presentation bullet points with real-world facts.

Topic: {topic}
Slide Title: {slide_title}
Original Bullets: {original_bullets}

Web Research Results:
{search_results}

Using the research results above, improve the bullet points.
Keep the same slide structure but make bullets more factual and specific.

RULES:
- Return exactly {num_bullets} bullet points
- Each bullet must be 12 words or fewer
- Use real data/facts from the research when relevant
- Keep bullets concise and presentation-ready

Respond with ONLY a JSON array of strings:
["improved bullet 1", "improved bullet 2", "improved bullet 3"]

No extra text. Only the JSON array."""


class AutoPPTAgent:
    """
    The main agent that orchestrates presentation creation.

    Flow: PLAN --> EXECUTE (loop) --> OBSERVE --> SAVE
    """

    def __init__(self):
        self.llm = InferenceClient(api_key=HF_API_KEY)
        self.model = "Qwen/Qwen2.5-72B-Instruct"
        self.ppt_client = MCPClient()
        self.search_client = MCPClient()  # Second MCP server for web search
        self.execution_log = []  # Observation log

    # ──────────────────────────────────────────────────────────────────────
    # LLM Call Helper
    # ──────────────────────────────────────────────────────────────────────

    def _call_llm(self, system_prompt: str, user_message: str, max_tokens: int = 1500) -> str:
        """Send a message to the LLM and return the response text."""
        try:
            response = self.llm.chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self._log(f"LLM call failed: {e}")
            return ""

    # ──────────────────────────────────────────────────────────────────────
    # Logging / Observation
    # ──────────────────────────────────────────────────────────────────────

    def _log(self, message: str):
        """Log an observation."""
        self.execution_log.append(message)
        print(f"  [AGENT] {message}")

    # ──────────────────────────────────────────────────────────────────────
    # Step 5: PLANNING
    # ──────────────────────────────────────────────────────────────────────

    def _detect_slide_count(self, prompt: str) -> int:
        """Extract the number of slides from the user prompt, default to 5."""
        # Look for patterns like "5 slides", "7-slide", "10 slide"
        match = re.search(r"(\d+)\s*[-\s]?slides?", prompt, re.IGNORECASE)
        if match:
            count = int(match.group(1))
            # Clamp between 3 and 15
            return max(3, min(count, 15))
        return 5  # Default

    def _parse_plan_json(self, raw_response: str) -> dict:
        """
        Parse the LLM's response into a structured plan.
        Implements robust fallback parsing for unreliable LLM output.
        """
        # Strategy 1: Direct JSON parse
        try:
            plan = json.loads(raw_response)
            if "slides" in plan and "presentation_title" in plan:
                return plan
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract JSON from markdown code fences
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
        if json_match:
            try:
                plan = json.loads(json_match.group(1))
                if "slides" in plan and "presentation_title" in plan:
                    return plan
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find the first { ... } block
        brace_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if brace_match:
            try:
                plan = json.loads(brace_match.group(0))
                if "slides" in plan:
                    if "presentation_title" not in plan:
                        plan["presentation_title"] = plan.get("title", "Presentation")
                    return plan
            except json.JSONDecodeError:
                pass

        # Strategy 4: Regex extraction of slide titles and bullets
        self._log("JSON parsing failed. Using regex fallback.")
        slides = []
        # Look for numbered items like "1. Title" or "Slide 1: Title"
        slide_pattern = re.findall(
            r"(?:slide\s*\d+[:\-.]?\s*|(\d+)[.\)]\s*)([^\n]+)",
            raw_response,
            re.IGNORECASE,
        )
        for _, title in slide_pattern:
            title = title.strip().strip('"').strip("'")
            if title and len(title) > 2:
                slides.append({"title": title, "bullets": []})

        if slides:
            return {
                "presentation_title": slides[0]["title"] if slides else "Presentation",
                "slides": slides,
            }

        # Strategy 5: Complete failure -- return None
        return None

    def _validate_plan(self, plan: dict, num_slides: int) -> dict:
        """Validate and fix the plan to meet slide content rules."""
        if not plan or "slides" not in plan:
            return None

        # Ensure presentation_title exists
        if not plan.get("presentation_title"):
            plan["presentation_title"] = "Presentation"

        validated_slides = []
        for slide in plan["slides"][:num_slides]:
            title = slide.get("title", "Untitled Slide")

            bullets = slide.get("bullets", [])
            if not isinstance(bullets, list):
                bullets = [str(bullets)]

            # Filter out empty bullets
            bullets = [b for b in bullets if b and str(b).strip()]

            # Truncate each bullet to 12 words
            cleaned = []
            for b in bullets:
                words = str(b).strip().split()
                if len(words) > 12:
                    words = words[:12]
                cleaned.append(" ".join(words))

            # Enforce 3-5 bullets
            if len(cleaned) > 5:
                cleaned = cleaned[:5]

            validated_slides.append({
                "title": title,
                "bullets": cleaned,
            })

        plan["slides"] = validated_slides
        return plan

    def plan(self, prompt: str) -> dict:
        """
        Step 5: Generate a structured plan from the user prompt.

        Returns a dict with 'presentation_title' and 'slides' list.
        """
        self._log("=" * 50)
        self._log("PHASE 1: PLANNING")
        self._log("=" * 50)
        self._log(f"User prompt: {prompt}")

        num_slides = self._detect_slide_count(prompt)
        self._log(f"Target slide count: {num_slides}")

        # Call the LLM to generate a plan
        system_prompt = PLANNING_PROMPT.format(num_slides=num_slides)
        raw_response = self._call_llm(system_prompt, prompt)

        if not raw_response:
            self._log("LLM returned empty response. Generating fallback plan.")
            return self._generate_fallback_plan(prompt, num_slides)

        self._log(f"LLM raw response length: {len(raw_response)} chars")

        # Parse the response
        plan = self._parse_plan_json(raw_response)

        if plan is None:
            self._log("All parsing strategies failed. Using fallback plan.")
            return self._generate_fallback_plan(prompt, num_slides)

        # Validate and fix
        plan = self._validate_plan(plan, num_slides)

        if plan is None or not plan.get("slides"):
            self._log("Validation failed. Using fallback plan.")
            return self._generate_fallback_plan(prompt, num_slides)

        # Fill in missing bullets using LLM
        for slide in plan["slides"]:
            if len(slide["bullets"]) < 3:
                self._log(f"Slide '{slide['title']}' has {len(slide['bullets'])} bullets. Generating more...")
                slide["bullets"] = self._generate_bullets(
                    prompt, slide["title"], max(3, 4 - len(slide["bullets"]))
                )

        self._log(f"Plan created: '{plan['presentation_title']}' with {len(plan['slides'])} slides")
        for i, s in enumerate(plan["slides"]):
            self._log(f"  Slide {i + 1}: {s['title']} ({len(s['bullets'])} bullets)")

        return plan

    def _generate_bullets(self, topic: str, slide_title: str, num_bullets: int = 4) -> list:
        """Use the LLM to generate bullet points for a slide."""
        system_prompt = CONTENT_ENHANCEMENT_PROMPT.format(
            topic=topic, slide_title=slide_title, num_bullets=num_bullets
        )
        raw = self._call_llm(system_prompt, f"Generate bullets for: {slide_title}")

        # Try to parse as JSON array
        try:
            bullets = json.loads(raw)
            if isinstance(bullets, list):
                return [str(b).strip() for b in bullets if b][:5]
        except json.JSONDecodeError:
            pass

        # Fallback: extract lines
        lines = [l.strip().lstrip("-*0123456789.) ") for l in raw.split("\n") if l.strip()]
        if lines:
            return lines[:5]

        # Ultimate fallback
        return [
            f"Key aspect of {slide_title}",
            f"Important detail about {slide_title}",
            f"Notable fact regarding {slide_title}",
        ]

    def _generate_fallback_plan(self, prompt: str, num_slides: int) -> dict:
        """Generate a basic plan when the LLM fails completely."""
        # Extract a clean topic from the prompt
        topic = prompt.strip()
        # Remove common prefixes to get the core topic
        prefixes = [
            "create a presentation on", "create a presentation about",
            "make a presentation on", "make a presentation about",
            "create a ppt on", "create a ppt about",
            "make a ppt on", "make a ppt about",
            "make slides on", "make slides about",
            "present on", "present about",
            "create slides on", "create slides about",
            "presentation on", "presentation about",
        ]
        lower_topic = topic.lower()
        for prefix in prefixes:
            if lower_topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        # Also remove leading slide count like "5-slide ", "7 slides on "
        topic = re.sub(r'^\d+\s*-?\s*slides?\s*(on|about)?\s*', '', topic, flags=re.IGNORECASE).strip()
        # Remove leading articles
        topic = re.sub(r'^(a|an|the)\s+', '', topic, flags=re.IGNORECASE).strip()

        title = topic.title() if topic else "Presentation"

        slide_titles = [
            f"Introduction to {title}",
            f"Key Concepts of {title}",
            f"Applications of {title}",
            f"Benefits and Advantages",
            f"Challenges and Future Trends",
            f"Real-World Examples",
            f"Best Practices",
            f"Summary and Conclusion",
        ]

        slides = []
        for i in range(min(num_slides, len(slide_titles))):
            slides.append({
                "title": slide_titles[i],
                "bullets": [
                    f"Key point about {slide_titles[i].lower()}",
                    f"Important aspect to consider",
                    f"Notable information for audience",
                ],
            })

        plan = {
            "presentation_title": title,
            "slides": slides,
        }

        # Try to enhance bullets with LLM
        for slide in plan["slides"]:
            enhanced = self._generate_bullets(topic, slide["title"], 4)
            if enhanced and len(enhanced) >= 3:
                slide["bullets"] = enhanced

        self._log(f"Fallback plan generated: {len(slides)} slides on '{title}'")
        return plan

    # ──────────────────────────────────────────────────────────────────────
    # Step 7: RESEARCH (Web Search via MCP)
    # ──────────────────────────────────────────────────────────────────────

    async def research(self, plan: dict, topic: str) -> dict:
        """
        Step 7: Use the Search MCP Server to gather real-world information
        and enhance slide content with factual data.

        Args:
            plan: The structured plan from the planning phase.
            topic: The user's original topic.

        Returns:
            The enhanced plan with improved bullet points.
        """
        self._log("")
        self._log("=" * 50)
        self._log("PHASE 2: RESEARCH (Web Search MCP)")
        self._log("=" * 50)

        try:
            # Connect to the Search MCP Server
            self._log("Connecting to Search MCP Server...")
            await self.search_client.connect("search")

            # Search for the main topic
            query = topic.strip()
            self._log(f"Searching web for: '{query}'")

            result = await self.search_client.call_tool("search_web", {
                "query": query,
            })
            search_data = json.loads(result)
            self._log(f"Search status: {search_data.get('status', 'unknown')}")

            results = search_data.get("results", [])
            if not results:
                self._log("No search results found. Skipping enhancement.")
                return plan

            self._log(f"Found {len(results)} search results.")
            for i, r in enumerate(results):
                self._log(f"  [{i+1}] {r.get('title', 'No title')}")

            # Format search results as text for the LLM
            search_text = ""
            for r in results:
                search_text += f"Title: {r.get('title', '')}\n"
                search_text += f"Snippet: {r.get('snippet', '')}\n\n"

            # Enhance each slide's bullets using the search results
            enhanced_count = 0
            for slide in plan["slides"]:
                self._log(f"Enhancing slide: '{slide['title']}'...")

                system_prompt = RESEARCH_ENHANCEMENT_PROMPT.format(
                    topic=topic,
                    slide_title=slide["title"],
                    original_bullets=json.dumps(slide["bullets"]),
                    search_results=search_text,
                    num_bullets=len(slide["bullets"]),
                )

                raw = self._call_llm(
                    system_prompt,
                    f"Enhance bullets for: {slide['title']}",
                )

                # Try to parse the enhanced bullets
                try:
                    enhanced = json.loads(raw)
                    if isinstance(enhanced, list) and len(enhanced) >= 3:
                        # Truncate each bullet to 12 words
                        cleaned = []
                        for b in enhanced:
                            words = str(b).strip().split()
                            if len(words) > 12:
                                words = words[:12]
                            cleaned.append(" ".join(words))
                        slide["bullets"] = cleaned[:5]
                        enhanced_count += 1
                        self._log(f"  -> Enhanced with {len(cleaned[:5])} fact-based bullets.")
                    else:
                        self._log(f"  -> LLM returned insufficient bullets. Keeping original.")
                except json.JSONDecodeError:
                    self._log(f"  -> Could not parse enhanced bullets. Keeping original.")

            self._log(f"Research complete: {enhanced_count}/{len(plan['slides'])} slides enhanced.")
            return plan

        except FileNotFoundError:
            self._log("Search MCP Server not found. Skipping research phase.")
            return plan
        except Exception as e:
            self._log(f"Research phase failed: {e}. Continuing with original plan.")
            return plan
        finally:
            try:
                await self.search_client.close()
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────────
    # Step 6: EXECUTION LOOP
    # ──────────────────────────────────────────────────────────────────────

    async def execute(self, plan: dict) -> str:
        """
        Step 6: Execute the plan by calling MCP tools in a loop.

        Flow: CREATE --> ADD SLIDE --> OBSERVE --> NEXT --> ... --> SAVE

        Returns the path to the saved .pptx file.
        """
        self._log("")
        self._log("=" * 50)
        self._log("PHASE 3: EXECUTION")
        self._log("=" * 50)

        # Connect to the PPT MCP Server
        self._log("Connecting to PPT MCP Server...")
        await self.ppt_client.connect("ppt")

        try:
            # ── Step 1: Create Presentation ──
            self._log("")
            self._log("--- Action: create_presentation ---")
            result = await self.ppt_client.call_tool("create_presentation", {
                "title": plan["presentation_title"],
            })
            observation = json.loads(result)
            self._log(f"Observation: {observation['message']}")

            if observation.get("status") != "success":
                self._log("FATAL: Could not create presentation!")
                return None

            # ── Step 2: Add slides one by one ──
            for i, slide in enumerate(plan["slides"]):
                self._log("")
                self._log(f"--- Action: add_slide ({i + 1}/{len(plan['slides'])}) ---")
                self._log(f"  Title  : {slide['title']}")
                self._log(f"  Bullets: {len(slide['bullets'])} points")

                result = await self.ppt_client.call_tool("add_slide", {
                    "title": slide["title"],
                    "bullets": json.dumps(slide["bullets"]),
                })
                observation = json.loads(result)
                self._log(f"Observation: {observation['message']}")

                if observation.get("status") != "success":
                    self._log(f"WARNING: Slide {i + 1} may have issues. Continuing...")

                # ── Observe: Check slide count ──
                count_result = await self.ppt_client.call_tool("get_slide_count", {})
                count_data = json.loads(count_result)
                expected = i + 2  # title slide + slides added so far
                actual = count_data.get("slide_count", 0)
                self._log(f"Observation: Slide count = {actual} (expected {expected})")

                if actual != expected:
                    self._log("WARNING: Slide count mismatch!")

            # ── Step 3: Save Presentation ──
            self._log("")
            self._log("--- Action: save_presentation ---")
            # Generate a clean filename from the title
            safe_title = re.sub(r"[^a-zA-Z0-9\s]", "", plan["presentation_title"])
            safe_title = "_".join(safe_title.strip().split())
            filename = f"{safe_title}.pptx" if safe_title else "presentation.pptx"

            result = await self.ppt_client.call_tool("save_presentation", {
                "filename": filename,
            })
            observation = json.loads(result)
            self._log(f"Observation: {observation['message']}")

            filepath = observation.get("filepath", "")
            if observation.get("status") == "success":
                self._log(f"File saved: {filepath}")
            else:
                self._log("ERROR: Failed to save presentation!")
                filepath = None

            return filepath

        finally:
            # Always close the MCP connection
            await self.ppt_client.close()

    # ──────────────────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────────────────

    async def run(self, prompt: str) -> str:
        """
        Full pipeline: PLAN --> RESEARCH --> EXECUTE --> SAVE

        Args:
            prompt: The user's request (e.g., "Create a 5-slide presentation on AI")

        Returns:
            Path to the generated .pptx file, or None on failure.
        """
        self.execution_log = []

        self._log("Auto-PPT Agent Starting...")
        self._log(f"Prompt: {prompt}")
        self._log("")

        # Phase 1: Plan
        plan = self.plan(prompt)

        if not plan or not plan.get("slides"):
            self._log("FATAL: Could not generate a plan. Aborting.")
            return None

        # Phase 2: Research (enrich content via Search MCP Server)
        plan = await self.research(plan, prompt)

        # Phase 3: Execute
        filepath = await self.execute(plan)

        # Summary
        self._log("")
        self._log("=" * 50)
        self._log("COMPLETE")
        self._log("=" * 50)

        if filepath:
            self._log(f"Presentation saved to: {filepath}")
            self._log(f"Total slides: {len(plan['slides']) + 1} (including title)")
        else:
            self._log("Presentation generation failed.")

        return filepath
