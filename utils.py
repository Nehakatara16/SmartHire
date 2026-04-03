import PyPDF2
import docx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


#  Extract PDF
def extract_text_from_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        pdf = PyPDF2.PdfReader(file)
        for page in pdf.pages:
            if page.extract_text():
                text += page.extract_text()
    return text


#  Extract DOCX
def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])


#  Skills Extraction
def extract_skills(text):
    skills = ["python", "java", "sql", "machine learning", "flask", "html", "css"]
    text = text.lower()
    return [s for s in skills if s in text]


#  LOAD BEST MODEL (FAST + ACCURATE)
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


# GET EMBEDDING
def get_embedding(text):
    return model.encode(text)


#  MATCH RESUMES WITH JOB DESCRIPTION
def bert_match(resumes, job_desc):
    job_emb = get_embedding(job_desc)

    scores = []

    for res in resumes:
        res_emb = get_embedding(res)

        score = cosine_similarity(
            [res_emb],
            [job_emb]
        )[0][0]

        scores.append(float(round(score * 100, 2))) 

    return scores