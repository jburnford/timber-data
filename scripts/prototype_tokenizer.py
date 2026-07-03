#!/usr/bin/env python3
"""
Prototype: LLM-guided tokenization for dense shipping data.

Tests whether Gemini can identify ship/cargo boundaries without hallucinating content.
Key: All tokens must exist VERBATIM in the original text.
"""

import os
import json
import re
import google.generativeai as genai

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

genai.configure(api_key=API_KEY)

TOKENIZE_PROMPT = """You are parsing 19th century timber shipping records.

For the line below, identify ALL ships and their cargo. Return a JSON structure.

CRITICAL RULES:
1. Every text value MUST be copied EXACTLY from the original - no rewording
2. Multiple ships may appear in one line, separated by periods or new ship names
3. Each ship has: name, origin port, and one or more cargo items
4. Each cargo item has: quantity (optional), unit (optional), commodity, merchant
5. Ship names often have (s) for steamship
6. @ or — separates ship name from origin port
7. Semicolons often separate cargo items within same ship
8. "Order" means no specific merchant named

Return JSON format:
{
  "ships": [
    {
      "ship_name": "exact text from line",
      "origin_port": "exact text from line",
      "cargo": [
        {
          "quantity": "exact text or null",
          "unit": "exact text or null",
          "commodity": "exact text",
          "merchant": "exact text or null"
        }
      ]
    }
  ],
  "unparseable_segments": ["any text that doesn't fit ship/cargo pattern"],
  "parse_confidence": "high/medium/low"
}

LINE TO PARSE:
"""

# Test lines from 1875 dense format
TEST_LINES = [
    # Line 41 - Two ships, multiple cargo each
    "April 16. Empress (s) @ Trieste,—1,300 staves, Nickols & Colven; 41,500 staves, H. & R. Fowler; 9,173 staves, Oppenheimer & Co. Noumea @ Madras, &c.,—22,313 pcs. redwood, two logs sapanwood, Order.",

    # Line 45 - Two ships, cleaner format
    "April 21. Albert Edward (s) @ Gothenburg,—14 bxs. firewood, Stahlgren; 235 doz. battens, 380 doz. boards, 25 fms. firewood, 40 prs. oars, Order. Avena (s) @ Uddewalla,—3,720 bdls. mouldings, Esdaile & Co.",

    # Line 44 - Ships plus editorial content mixed in
    "April 20. Caroline @ Gothenburg,—1,135 doz. deals, Order. Neptionus @ Sannesund,—151 t. firewood, Order. A quantity of sapanwood was brought to the docks in barges from the wreck of the Border Chieftain at Dover.",
]


def verify_tokens_in_original(result: dict, original_line: str) -> dict:
    """Check that all extracted tokens exist verbatim in the original line."""
    verification = {
        "total_tokens": 0,
        "verified_tokens": 0,
        "failed_tokens": []
    }

    for ship in result.get("ships", []):
        # Check ship name
        if ship.get("ship_name"):
            verification["total_tokens"] += 1
            if ship["ship_name"] in original_line:
                verification["verified_tokens"] += 1
            else:
                verification["failed_tokens"].append(("ship_name", ship["ship_name"]))

        # Check origin port
        if ship.get("origin_port"):
            verification["total_tokens"] += 1
            if ship["origin_port"] in original_line:
                verification["verified_tokens"] += 1
            else:
                verification["failed_tokens"].append(("origin_port", ship["origin_port"]))

        # Check cargo items
        for cargo in ship.get("cargo", []):
            for field in ["quantity", "unit", "commodity", "merchant"]:
                if cargo.get(field):
                    verification["total_tokens"] += 1
                    if cargo[field] in original_line:
                        verification["verified_tokens"] += 1
                    else:
                        verification["failed_tokens"].append((field, cargo[field]))

    verification["accuracy"] = (
        verification["verified_tokens"] / verification["total_tokens"] * 100
        if verification["total_tokens"] > 0 else 0
    )

    return verification


def test_tokenization(model, line: str) -> dict:
    """Test tokenization on a single line."""
    prompt = TOKENIZE_PROMPT + line

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Clean JSON from markdown code blocks
        if response_text.startswith("```"):
            response_text = re.sub(r'^```\w*\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)

        result = json.loads(response_text)
        verification = verify_tokens_in_original(result, line)

        return {
            "status": "success",
            "result": result,
            "verification": verification
        }

    except json.JSONDecodeError as e:
        return {
            "status": "json_error",
            "error": str(e),
            "raw_response": response_text[:500] if 'response_text' in locals() else None
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def main():
    print("Initializing Gemini...")
    model = genai.GenerativeModel('gemini-2.0-flash')

    print("\n" + "="*80)
    print("TOKENIZATION PROTOTYPE TEST")
    print("="*80)

    for i, line in enumerate(TEST_LINES):
        print(f"\n{'='*80}")
        print(f"TEST LINE {i+1}:")
        print(f"{'='*80}")
        print(f"Original: {line[:100]}...")
        print()

        result = test_tokenization(model, line)

        if result["status"] == "success":
            parsed = result["result"]
            verification = result["verification"]

            print(f"Ships found: {len(parsed.get('ships', []))}")
            print(f"Parse confidence: {parsed.get('parse_confidence', 'N/A')}")
            print(f"Unparseable: {parsed.get('unparseable_segments', [])}")
            print()

            for j, ship in enumerate(parsed.get("ships", [])):
                print(f"  Ship {j+1}: {ship.get('ship_name', 'N/A')}")
                print(f"    Origin: {ship.get('origin_port', 'N/A')}")
                print(f"    Cargo items: {len(ship.get('cargo', []))}")
                for k, cargo in enumerate(ship.get("cargo", [])):
                    qty = cargo.get("quantity", "")
                    unit = cargo.get("unit", "")
                    comm = cargo.get("commodity", "")
                    merch = cargo.get("merchant", "Order" if not cargo.get("merchant") else cargo["merchant"])
                    print(f"      [{k+1}] {qty} {unit} {comm} → {merch}")

            print()
            print(f"VERIFICATION:")
            print(f"  Tokens checked: {verification['total_tokens']}")
            print(f"  Tokens verified: {verification['verified_tokens']}")
            print(f"  Accuracy: {verification['accuracy']:.1f}%")
            if verification["failed_tokens"]:
                print(f"  FAILED TOKENS:")
                for field, value in verification["failed_tokens"][:5]:
                    print(f"    - {field}: '{value}'")
        else:
            print(f"ERROR: {result['status']}")
            print(f"  {result.get('error', 'Unknown error')}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
