import pandas as pd
import requests
from pathlib import Path
from tqdm import tqdm

allowed_fields = ["Computer Science", "Mathematics", "Statistics", "Unknown"]
ollama_url = "http://localhost:11434/api/generate"
CLEANED_WEBSITE_PATH = "../data/faculty_websites_cleaned"


def submit_prompt(prompt):
    payload = {
        "model": "llama3.1:8b-instruct-fp16",
        "system": "You are an expert investigator with years of experience in online profiling and text analysis. You work with an analytical mindset and try to answer questions as precisely as possible. You can look at raw unstructured website texts and filter out irrelevant information.",
        "prompt": prompt,
        "stream": False,
        "options": {
            "seed": 47,
            "temperature": 0,
        },
    }
    return requests.post(ollama_url, json=payload).json()["response"]


def summarize_website(text, name, title, college):
    prompt = f"""I will give you a piece of text from the website of {name} who is a/an {title} at {college}.
The person's focus is either Computer Science, Mathematics, Statistics, or some other related field.
Your job is to correctly extract all of their research and teaching areas.
There can be a lot of irrelevant text and strange formatting since this is crawled from a website.
Your output should be a comma-separated list of academic fields.
Do not include too general fields like Computer Science or Mathematics.
Do not be too specific either, and only include high-level areas.
If there is not enough information, simply says Unknown, do not ask for more information.
Do not include your reasoning, just output a list.
You MUST follow the example output format below:

Examples of valid output:
Example 1: Computer Security, Privacy, Machine Learning
Example 2: Knot Theory, Linear Algebra
Example 3: Unknown

Examples of invalid output:
Example 1: Mathematics
Example 2: Computer Science
Example 3: Statistics, Computer Science
Example 4: Mathematics: Unknown
Example 5: Algebra, Probability, Unknown
    
Here's the text:
<START OF TEXT>
{text}
<END OF TEXT>

Your answer (DO NOT output "Computer Science" or "Mathematics" or "Statistics". DO NOT include "Unknown" if there are relevant fields. The output MUST be in a single line separated by comma. Do not include unncessary explanation.):
"""
    return submit_prompt(prompt)


def classify_field(summary):
    prompt = f"""I will give you a list containing one or more academic areas.
Which field do the majority of the areas belong to?
Choose either Computer Science or Mathematics or Statistics only.
If the information provided is insufficient or irrelevant, simply output Unknown.
If there are multiple possible choices, just output the best guess.
Do not explain your reasoning, just follow the format of the examples below.

Examples:
Input: Graphics, Video Games
Output: Computer Science

Input: Linear Algebra, Probabilities
Output: Mathematics

Input: Unknown
Output: Unknown

Here's the list of areas:
{summary}
"""
    return submit_prompt(prompt)


if __name__ == "__main__":
    faculty_orig = pd.read_csv("../data/faculty_list.csv")
    faculty_orig["field"] = ""
    faculty_orig["subfield"] = ""
    faculty = faculty_orig[pd.notna(faculty_orig["url"])]

    for i, row in tqdm(faculty.iterrows(), total=faculty.shape[0]):
        name = row["name"]
        title = row["title"]
        college = row["college"]
        path = Path(f"{CLEANED_WEBSITE_PATH}/{college}/{name}.txt")
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf8")

        summary = summarize_website(text, name, title, college)
        if summary is None:
            continue

        print(f"**************** {name}, {college} *****************")
        print(summary)

        fields = list(map(lambda f: f.strip(), summary.split(",")))
        text = " ".join(text.split("\n")).lower()
        new_fields = []
        for field in fields:
            field = field.lower()
            if (
                any([t == field for t in ["computer science", "mathematics", "statistics"]])
                or field not in text
                or any(
                    [
                        t in field
                        for t in [
                            "phd",
                            "ph.d"
                            "university",
                            "college",
                            "professor",
                            "lecturer",
                            "director",
                            "instructor",
                            "chair",
                            "introduct",
                            "independent research",
                        ]
                    ]
                )
            ):
                continue
            new_fields.append(field)
        print(new_fields)

        if len(new_fields) == 0:
            new_fields_str = "Unknown"
            classification = "Unknown"
        else:
            new_fields_str = ",".join(new_fields)
            classification = classify_field(new_fields_str)

        print(classification)
        classification = classification.lower()
        if "computer science" in classification:
            classification = "Computer Science"
        elif "mathematics" in classification:
            classification = "Mathematics"
        elif "statistics" in classification:
            classification = "Statistics"
        elif "unknown" in classification:
            classification = "Unknown"
        else:
            classification = "Invalid"

        faculty_orig.loc[
            (faculty_orig["name"] == name) & (faculty_orig["college"] == college),
            "field",
        ] = classification
        faculty_orig.loc[
            (faculty_orig["name"] == name) & (faculty_orig["college"] == college),
            "subfield",
        ] = new_fields_str

    faculty_orig.to_csv("../data/faculty_list_with_fields.csv", index=False)
