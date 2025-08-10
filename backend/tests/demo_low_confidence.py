"""
Demonstration of low confidence flagging functionality.
Shows how fields are flagged based on confidence scores.
"""

from app.routers.documents import is_low_confidence


def demo_low_confidence_flagging():
    """Demonstrate the low confidence flagging logic"""
    
    print("=== Low Confidence Flagging Demo ===\n")
    
    # Test various confidence scores
    test_cases = [
        (None, "No confidence score"),
        (0.0, "Zero confidence"),
        (0.3, "Low confidence (0.3)"),
        (0.65, "Below threshold (0.65)"),
        (0.69, "Just below threshold (0.69)"),
        (0.7, "Exactly at threshold (0.7)"),
        (0.71, "Just above threshold (0.71)"),
        (0.8, "Good confidence (0.8)"),
        (0.95, "High confidence (0.95)"),
        (1.0, "Perfect confidence (1.0)")
    ]
    
    print("Testing confidence scores against threshold (< 0.7):\n")
    print(f"{'Confidence':<20} {'Description':<25} {'Is Low Confidence'}")
    print("-" * 70)
    
    for confidence, description in test_cases:
        is_low = is_low_confidence(confidence)
        conf_str = str(confidence) if confidence is not None else "None"
        print(f"{conf_str:<20} {description:<25} {is_low}")
    
    print("\n=== Summary ===")
    print("✅ Fields with confidence >= 0.7 are NOT flagged as low confidence")
    print("🚩 Fields with confidence < 0.7 ARE flagged as low confidence")
    print("🚩 Fields with no confidence (None) ARE flagged as low confidence")
    print("\nThis helps users identify fields that may need manual review.")


if __name__ == "__main__":
    demo_low_confidence_flagging()