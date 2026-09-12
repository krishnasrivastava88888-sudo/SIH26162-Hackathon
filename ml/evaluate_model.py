import os
import joblib
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
from feature_engineering import load_dataset

MODEL_PATH = "ml/models/thermoguard_rf.pkl"
DATA_DIR = "ml/data"


def evaluate():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Train the model first using train_model.py")

    bundle = joblib.load(MODEL_PATH)
    pipeline = bundle["pipeline"]
    test_indices = bundle["test_indices"]

    df = load_dataset()
    X_test = df.drop(columns=["classification"]).iloc[test_indices]
    y_test = df["classification"].iloc[test_indices]

    y_pred = pipeline.predict(X_test)

    print("\n" + "=" * 55)
    print("  THERMOGUARD AI - INDEPENDENT SPATIAL TEST EVALUATION")
    print("=" * 55)
    print(classification_report(y_test, y_pred, zero_division=0))

    cm = confusion_matrix(y_test, y_pred, labels=pipeline.classes_)
    cm_df = pd.DataFrame(cm, index=pipeline.classes_, columns=pipeline.classes_)
    print("Confusion Matrix:\n", cm_df)

    # Extract Feature Importances
    rf = pipeline.named_steps["classifier"]
    feature_names = pipeline.named_steps["preprocessor"].feature_columns
    importances = rf.feature_importances_

    fi_df = pd.DataFrame({
        "feature": feature_names,
        "importance": importances
    }).sort_values(by="importance", ascending=False)

    fi_csv_path = os.path.join(DATA_DIR, "feature_importance.csv")
    fi_df.to_csv(fi_csv_path, index=False)
    print(f"\nFeature importances saved to: {fi_csv_path}")

    # Generate visual plot
    plt.figure(figsize=(8, 4.5))
    plt.barh(fi_df["feature"][::-1], fi_df["importance"][::-1], color="#0284c7")
    plt.xlabel("Gini Importance Score")
    plt.title("ThermoGuard Random Forest - Feature Importance")
    plt.tight_layout()
    plot_path = os.path.join(DATA_DIR, "feature_importance.png")
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"Plot saved to: {plot_path}")


if __name__ == "__main__":
    evaluate()