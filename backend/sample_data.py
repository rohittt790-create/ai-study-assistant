import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
if IS_SERVERLESS:
    UPLOADS_DIR = "/tmp/study_assistant_uploads"
else:
    UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

try:
    os.makedirs(UPLOADS_DIR, exist_ok=True)
except Exception:
    UPLOADS_DIR = "/tmp/study_assistant_uploads"
    os.makedirs(UPLOADS_DIR, exist_ok=True)

def create_sample_ai_pdf() -> str:
    pdf_path = os.path.join(UPLOADS_DIR, "CS101_AI_and_Machine_Learning_Notes.pdf")
    if os.path.exists(pdf_path):
        return pdf_path
        
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=14
    )
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading2'],
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#2563eb"),
        spaceBefore=12,
        spaceAfter=8
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    )
    
    story = []
    
    # Page 1
    story.append(Paragraph("CS101: Artificial Intelligence & Machine Learning", title_style))
    story.append(Paragraph("<b>Course</b>: Computer Science Tripos | <b>Semester</b>: Fall 2026", body_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Chapter 1: Foundations of Artificial Intelligence", h1_style))
    story.append(Paragraph(
        "Artificial Intelligence is defined as the simulation of human intelligence processes by computer systems, including learning, reasoning, and self-correction. "
        "The origin of modern AI traces back to Alan Turing's 1950 seminal paper proposing the Turing Test as a benchmark for machine cognitive capability.",
        body_style
    ))
    story.append(Paragraph(
        "A rational agent is defined as an autonomous entity that directs its activity towards achieving the best outcome or, when there is uncertainty, the best expected outcome. "
        "In modern computer science, AI is divided into Narrow AI (specialized systems designed for dedicated tasks such as chess or image classification) and General AI (hypothetical systems possessing versatile human-level adaptability across any intellectual domain).",
        body_style
    ))
    story.append(Paragraph(
        "Search algorithms form the cornerstone of early AI problem solving. The A* Search Algorithm is an informed search algorithm that computes f(n) = g(n) + h(n), where g(n) represents the actual cost from start to node n, and h(n) is an admissible heuristic estimating cost to the goal.",
        body_style
    ))
    story.append(PageBreak())
    
    # Page 2
    story.append(Paragraph("Chapter 2: Machine Learning Paradigms", h1_style))
    story.append(Paragraph(
        "Supervised Learning refers to training models on labeled datasets where the input features and target outputs are explicitly provided. "
        "Common algorithms in supervised learning include Linear Regression, Logistic Regression, Decision Trees, and Support Vector Machines.",
        body_style
    ))
    story.append(Paragraph(
        "Unsupervised Learning refers to discovering hidden patterns, clusters, or intrinsic structures in unlabeled data without predefined feedback. "
        "Principal Component Analysis (PCA) and K-Means Clustering are canonical unsupervised approaches.",
        body_style
    ))
    story.append(Paragraph(
        "Overfitting is defined as a modeling error that occurs when a machine learning algorithm captures noise along with the underlying pattern of data, resulting in poor generalization on unseen validation data. "
        "Techniques to prevent overfitting include L1/L2 Regularization, Cross-Validation, Dropout, and Early Stopping.",
        body_style
    ))
    story.append(Paragraph(
        "Reinforcement Learning is a paradigm where an autonomous agent learns optimal decision policies through iterative environmental interaction via trial-and-error reward signals.",
        body_style
    ))
    story.append(PageBreak())
    
    # Page 3
    story.append(Paragraph("Chapter 3: Deep Learning and Neural Networks", h1_style))
    story.append(Paragraph(
        "Deep Learning refers to a subset of machine learning based on artificial neural networks with multiple representation layers capable of learning hierarchical data representations.",
        body_style
    ))
    story.append(Paragraph(
        "The Artificial Neuron or Perceptron computes a linear combination of weighted inputs plus a bias term, passed through a non-linear activation function. "
        "The Rectified Linear Unit (ReLU) is defined as f(x) = max(0, x) and is widely favored because it mitigates the vanishing gradient problem during backpropagation.",
        body_style
    ))
    story.append(Paragraph(
        "Backpropagation is the process of calculating the gradient of the loss function with respect to each weight by applying the chain rule of calculus in reverse order through the network layers. "
        "Gradient Descent iteratively updates model parameters in the opposite direction of the gradient to minimize the empirical risk.",
        body_style
    ))
    story.append(Paragraph(
        "Convolutional Neural Networks (CNNs) specialize in grid-structured inputs such as computer vision images, leveraging shared kernel convolutions and spatial pooling layers.",
        body_style
    ))
    story.append(PageBreak())
    
    # Page 4
    story.append(Paragraph("Chapter 4: Natural Language Processing & Large Language Models", h1_style))
    story.append(Paragraph(
        "Natural Language Processing (NLP) is defined as the scientific study and engineering of computational systems that understand, interpret, and generate human languages.",
        body_style
    ))
    story.append(Paragraph(
        "Tokenization refers to the process of converting raw character sequences into subword or word units called tokens. "
        "Word Embeddings represent discrete words as dense, continuous vector spaces where semantic similarity correlates with geometric cosine proximity.",
        body_style
    ))
    story.append(Paragraph(
        "The Transformer Architecture introduced in 2017 replaced recurrence entirely with self-attention mechanisms. "
        "Self-Attention is defined as a mathematical mechanism that allows an input sequence element to dynamically weight and attend to every other position in the sequence.",
        body_style
    ))
    story.append(Paragraph(
        "Retrieval-Augmented Generation (RAG) is defined as an AI architectural pattern that enhances language model generation by querying external verified knowledge stores before generating grounded responses.",
        body_style
    ))
    
    doc.build(story)
    return pdf_path

if __name__ == "__main__":
    p = create_sample_ai_pdf()
    print("Created sample PDF at:", p)
