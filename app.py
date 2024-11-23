import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

# In-memory storage
questions = []
answers = {}
user_reputation = {}

# AI Model Configuration
generation_config = {
    "temperature": 2,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 512,
}

# Initialize the model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

@app.route("/")
def index():
    """Display all questions."""
    return render_template("index.html", questions=questions)


@app.route("/ask", methods=["GET", "POST"])
def ask_question():
    """Allow users to post a question and generate tags."""
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        user = request.form.get("user")

        # Generate tags using Gemini
        chat_session = model.start_chat(history=[])
        chat_session.send_message(
            "You are an AI model tasked with generating relevant tags for a question based on its content."
        )
        chat_session.send_message(f"Question: {content}")
        
        # Generate tags based on the question content
        tags_response = chat_session.send_message(
            "Please generate a list of 3-5 relevant tags for this question. Provide only the tags."
        ).text
        
        tags = [tag.strip() for tag in tags_response.split(",")]

        question_id = len(questions) + 1
        questions.append({
            "id": question_id,
            "title": title,
            "content": content,
            "user": user,
            "tags": tags,  # Store the generated tags
        })
        answers[question_id] = []  # Initialize the answers list for the new question
        return redirect(url_for("index"))
    return render_template("ask.html")


@app.route("/question/<int:question_id>", methods=["GET", "POST"])
def view_question(question_id):
    """Display a single question and its answers."""
    question = next((q for q in questions if q["id"] == question_id), None)
    if not question:
        return "Question not found.", 404

    # Ensure the answers list exists for the given question_id
    if question_id not in answers:
        answers[question_id] = []

    if request.method == "POST":
        user = request.form.get("user")
        user_response = request.form.get("response")

        # Gemini interaction for answer analysis
        chat_session = model.start_chat(history=[])
        chat_session.send_message(
            "You are an AI model tasked with analyzing answers based on clarity, correctness, and completeness."
        )
        chat_session.send_message(f"Question: {question['content']}")
        chat_session.send_message(f"Answer: {user_response or 'AI-generated answer'}")
        
        # Simplified analysis prompt for any answer type
        analysis_response = chat_session.send_message(
            "Please analyze the answer's clarity, correctness, and completeness. Provide a comment only."
        ).text
        
        # Log the raw response for debugging
        print("AI Analysis Response:", analysis_response)

        # Extract only the comment
        comment = analysis_response.strip()

        if not user_response:
            user_response = chat_session.send_message(question["content"]).text
            user = "AI"

        # Answer structure with comments
        response = {
            "user": user,
            "content": user_response,
            "upvotes": 0,
            "downvotes": 0,
            "analysis": comment,
            "comments": []  # Initialize comments for each answer
        }

        answers[question_id].append(response)

        # Update user reputation based on comment length/quality (optional)
        user_reputation[user] = user_reputation.get(user, 0) + len(comment.split())

    return render_template("question.html", question=question, answers=answers[question_id])


@app.route("/comment/<int:question_id>/<int:answer_index>", methods=["POST"])
def comment_on_answer(question_id, answer_index):
    """Allow users to comment on an answer."""
    try:
        comment_content = request.form.get("comment")
        if not comment_content:
            return jsonify({"success": False, "error": "Comment cannot be empty"}), 400

        answer = answers[question_id][answer_index]
        answer["comments"].append(comment_content)
        return jsonify({"success": True, "comment": comment_content})
    except IndexError:
        return jsonify({"success": False, "error": "Answer not found"}), 404


@app.route("/vote/<int:question_id>/<int:answer_index>/<vote_type>", methods=["POST"])
def vote(question_id, answer_index, vote_type):
    """Upvote or downvote an answer."""
    try:
        answer = answers[question_id][answer_index]
        if vote_type == "upvote":
            answer["upvotes"] += 1
        elif vote_type == "downvote":
            answer["downvotes"] += 1
        return jsonify({"success": True, "answer": answer})
    except IndexError:
        return jsonify({"success": False, "error": "Answer not found"}), 404


@app.route("/analytics")
def analytics():
    """Display basic analytics."""
    total_questions = len(questions)
    total_answers = sum(len(a) for a in answers.values())
    return render_template(
        "analytics.html",
        total_questions=total_questions,
        total_answers=total_answers,
        user_reputation=user_reputation,
    )


if __name__ == "__main__":
    app.run(debug=True)
