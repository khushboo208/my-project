import pandas as pd
import pickle
from sklearn.preprocessing import LabelEncoder

df = pd.read_csv("fashion_dataset/labels.csv")

main_encoder = LabelEncoder().fit(df["main_category"])
sub_encoder = LabelEncoder().fit(df["subcategory"])
color_encoder = LabelEncoder().fit(df["color"])

with open("main_encoder.pkl", "wb") as f:
    pickle.dump(main_encoder, f)

with open("sub_encoder.pkl", "wb") as f:
    pickle.dump(sub_encoder, f)

with open("color_encoder.pkl", "wb") as f:
    pickle.dump(color_encoder, f)

print("Encoders saved successfully.")
