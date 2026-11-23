import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# 1. Load dataset
df = pd.read_csv("dataset.csv")

# 2. Separate input and output
X = df["description"]
y = df["category"]

# 3. Split dataset
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.25,
    random_state=42,
    stratify=y
)

# 4. Create ML pipeline
model = Pipeline([
    ("vectorizer", TfidfVectorizer()),
    ("classifier", RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced"
    ))
])

# 5. Train model
model.fit(X_train, y_train)

# 6. Test model
predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)

print("MODEL TRAINED SUCCESSFULLY")
print("--------------------------------")
print("Accuracy:", round(accuracy * 100, 2), "%")

print("\nClassification Report:")
print(classification_report(y_test, predictions))

# 7. Save trained model
joblib.dump(model, "emergency_model.pkl")

print("\nModel saved as emergency_model.pkl")