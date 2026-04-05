"""
Test script for PPT MCP Server tools -- Step 2 & 3 Verification
===============================================================
This script directly calls the tool functions to verify they work
BEFORE we connect them to the agent via MCP protocol.

Run:  python -m mcp_servers.test_ppt_tools
"""

import sys
import os
import json

# Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from mcp_servers.ppt_server import (
    create_presentation,
    add_slide,
    get_slide_count,
    save_presentation,
)


def run_test():
    print("=" * 60)
    print("  PPT MCP Server -- Tool Test")
    print("=" * 60)

    # ---- Test 1: Create Presentation ----
    print("\n[TEST 1] create_presentation")
    result = create_presentation("Artificial Intelligence Overview")
    data = json.loads(result)
    print(f"   Status : {data['status']}")
    print(f"   Message: {data['message']}")
    print(f"   Slides : {data['slide_count']}")
    assert data["status"] == "success", "FAIL: create_presentation failed!"
    assert data["slide_count"] == 1, "FAIL: Should have 1 slide (title)"
    print("   >> PASSED")

    # ---- Test 2: Add Slides ----
    slides_data = [
        {
            "title": "What is AI?",
            "bullets": json.dumps([
                "AI simulates human intelligence in machines",
                "Includes learning, reasoning, and self-correction",
                "Used in healthcare, finance, and robotics",
                "Powers virtual assistants like Siri and Alexa",
            ]),
        },
        {
            "title": "Types of AI",
            "bullets": json.dumps([
                "Narrow AI: designed for specific tasks",
                "General AI: human-level cognitive abilities",
                "Super AI: surpasses human intelligence",
            ]),
        },
        {
            "title": "AI in Daily Life",
            "bullets": json.dumps([
                "Recommendation systems on Netflix and YouTube",
                "Voice assistants for smart home control",
                "Self-driving cars use computer vision",
                "AI chatbots handle customer support",
                "Fraud detection in banking systems",
            ]),
        },
    ]

    print("\n[TEST 2] add_slide (adding 3 slides)")
    for i, s in enumerate(slides_data):
        result = add_slide(s["title"], s["bullets"])
        data = json.loads(result)
        print(f"   Slide {i + 1}: {data['message']}")
        assert data["status"] == "success", f"FAIL: add_slide failed for slide {i + 1}!"
    print("   >> PASSED")

    # ---- Test 3: Get Slide Count ----
    print("\n[TEST 3] get_slide_count")
    result = get_slide_count()
    data = json.loads(result)
    print(f"   Total slides: {data['slide_count']}")
    assert data["slide_count"] == 4, "FAIL: Should have 4 slides (1 title + 3 content)"
    print("   >> PASSED")

    # ---- Test 4: Save Presentation ----
    print("\n[TEST 4] save_presentation")
    result = save_presentation("test_output.pptx")
    data = json.loads(result)
    print(f"   Status : {data['status']}")
    print(f"   File   : {data['filepath']}")
    assert data["status"] == "success", "FAIL: save_presentation failed!"
    assert os.path.exists(data["filepath"]), "FAIL: File was not created!"
    file_size = os.path.getsize(data["filepath"])
    print(f"   Size   : {file_size:,} bytes")
    print("   >> PASSED")

    # ---- Test 5: Edge case -- add_slide with no presentation ----
    print("\n[TEST 5] add_slide after save (should error gracefully)")
    result = add_slide("Ghost Slide", json.dumps(["This should fail"]))
    data = json.loads(result)
    print(f"   Status : {data['status']}")
    print(f"   Message: {data['message']}")
    assert data["status"] == "error", "FAIL: Should have returned error!"
    print("   >> PASSED")

    # ---- Test 6: Edge case -- bullet validation ----
    print("\n[TEST 6] Bullet validation (too many bullets, long text)")
    create_presentation("Edge Case Test")
    long_bullets = json.dumps([
        "This is a very long bullet point that exceeds the twelve word limit and should be truncated properly",
        "Second bullet",
        "Third bullet",
        "Fourth bullet",
        "Fifth bullet",
        "Sixth bullet that should be dropped",
        "Seventh bullet also dropped",
    ])
    result = add_slide("Validation Test", long_bullets)
    data = json.loads(result)
    print(f"   Status : {data['status']}")
    print(f"   Message: {data['message']}")
    # Should have exactly 5 bullets (truncated from 7)
    assert "5 bullet" in data["message"], "FAIL: Should have truncated to 5 bullets!"
    save_presentation("test_edge_cases.pptx")
    print("   >> PASSED")

    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED!")
    print("=" * 60)
    print("\n  Check the output/ folder for generated .pptx files:")
    print("   -> output/test_output.pptx")
    print("   -> output/test_edge_cases.pptx")


if __name__ == "__main__":
    run_test()
