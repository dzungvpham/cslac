import pandas as pd
import requests
from pathlib import Path
from tqdm import tqdm

faculty_orig = pd.read_csv("../data/faculty_list.csv")
faculty_orig["field"] = ""
faculty_orig["subfield"] = ""
faculty = faculty_orig[pd.notna(faculty_orig["url"])]

allowed_fields = ["Computer Science", "Mathematics", "Statistics", "Unknown"]

for i, row in tqdm(faculty.iterrows(), total=faculty.shape[0]):
    name = row["name"]
    title = row["title"]
    college = row["college"]
    path = Path(f"../data/faculty_websites/{college}/{name}.txt")
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf8")

    url = "http://localhost:11434/api/generate"
    summarize_prompt = f"""Given the following text from the website of {name} who is a/an {title} at {college}, summarize relevant information about the person, particularly their department (Computer Science, Mathematics, or Statistics), research and teaching interests, courses taught, and degree information. The text will start with <START_OF_TEXT> and end with <END_OF_TEXT>. Do not include anything unrelated to the person in the output. Do not include anything about the website. Write in bullet points. Focus on their research/teaching fields. Please be thorough.

<START_OF_TEXT>
{text}
<END_OF_TEXT>
"""

    payload = {
        "model": "llama3",
        "prompt": summarize_prompt,
        "stream": False,
        "options": {
            "seed": 47,
            "temperature": 0,
        }
    }

    summary = requests.post(url, json=payload).json()["response"]
    classify_prompt = f"""Below is the summary of a professor's website. Determine their research/teaching field and subfields. The field can be Computer Science, Mathematics, Statistics, or Unknown. Choose only one field. Do not include non-essential phrases like 'Here is the output' in the output. If the field is Unknown, do not include any explanation, just put Unknown. Write your output in a single sentence in a single line like this:

Example 1:
Computer Science: Security, Cryptography

Example 2:
Mathematics

Example 3:
Unknown

<START_OF_SUMMARY>
{summary}
<END_OF_SUMMARY>
"""
    
    payload = {
        "model": "llama3",
        "prompt": classify_prompt,
        "stream": False,
        "options": {
            "seed": 47,
            "temperature": 0,
        }
    }

    classification = requests.post(url, json=payload).json()["response"]
    lines = classification.split("\n")
    line = None
    if len(lines) > 1:
        for l in lines:
            if any([f in l for f in allowed_fields]):
                line = l
                break
    else:
        line = lines[0]
    if line is None:
        print(f"\nInvalid classification for {name} -- {college}: {classification}")
        continue
        
    field = ""
    subfield = ""

    if ":" in line:
        parts = line.split(":")
        field = parts[0].strip()
        if len(parts) > 2:
            print(f"\nInvalid classification for {name} -- {college}: {classification}")
            subfield = "".join(parts[1:])
        else:            
            subfield = parts[1].strip()
    else:
        field = line

    print(f"\n{name} -- {college}: {field} | {subfield}")
    if field not in allowed_fields:
        print("\nInvalid field!")

    faculty_orig.loc[
        (faculty_orig["name"] == name) & (faculty_orig["college"] == college), "field"
    ] = field
    faculty_orig.loc[
        (faculty_orig["name"] == name) & (faculty_orig["college"] == college), "subfield"
    ] = subfield

faculty_orig.to_csv("../data/faculty_list_with_fields.csv", index=False)

    
