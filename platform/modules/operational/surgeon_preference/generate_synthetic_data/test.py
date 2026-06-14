import pandas as pd
from generate_synthetic_data.clinical_mapping_logic import generate_clinical_mapping


def run_comprehensive_clinical_test(iterations=1000):
    print(f"🔄 Running {iterations} synthetic clinical iterations to verify constraints...\n")

    records = []
    errors = 0

    for i in range(iterations):
        try:
            case = generate_clinical_mapping()
            records.append({
                "subspecialty": case["subspecialty"],
                "procedure": case["procedure"]["name"],
                "drape_pack": case["drape_pack"],
                "skin_prep": case["skin_prep"],
                "positioning": case["positioning"],
                "has_implants": case["implants"] is not None,
                "first_implant": case["implants"][0] if case["implants"] else "None",
                "has_instruments": len(case["instruments"]) > 0
            })
        except Exception as e:
            errors += 1
            print(f"❌ Error on iteration {i}: {type(e).__name__} - {str(e)}")

    if errors > 0:
        print(f"\n🚨 Test Failed! {errors} iterations crashed.")
        return

    # Convert to Dataframe for easy cross-tabulation tracking
    df = pd.DataFrame(records)

    print("=========================================================================")
    print("📊 CLINICAL CROSS-VALIDATION SUMMARY")
    print("=========================================================================")

    # 1. Check Draping Mapping Accuracy
    print("\n1. Verification: Procedure ➡️ Drape Pack Alignment")
    drape_check = df.groupby(["procedure", "drape_pack"]).size().reset_index(name="count")
    print(drape_check.to_string(index=False))

    # 2. Check Implant Logical Guarding
    print("\n2. Verification: Subspecialty ➡️ Implant Presence")
    implant_check = df.groupby(["subspecialty", "has_implants"]).size().reset_index(name="count")
    print(implant_check.to_string(index=False))

    # 3. Check Specific Implant Assignment Matrix
    print("\n3. Verification: Procedure ➡️ Specific Implant Match")
    specific_implant_check = df.groupby(["procedure", "first_implant"]).size().reset_index(name="count")
    print(specific_implant_check.to_string(index=False))

    # 4. Check Skin Prep Constraints
    print("\n4. Verification: Subspecialty ➡️ Skin Prep Rule Check")
    prep_check = df.groupby(["subspecialty", "skin_prep"]).size().reset_index(name="count")
    print(prep_check.to_string(index=False))

    print("\n=========================================================================")
    print("✅ TEST COMPLETE: Review the tables above to confirm clinical accuracy.")
    print("=========================================================================")


if __name__ == "__main__":
    # Ensure you have pandas installed: pip install pandas
    run_comprehensive_clinical_test()
