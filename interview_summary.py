from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, BaseDocTemplate, PageTemplate, Frame
from reportlab.platypus import NextPageTemplate, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter
import io
import pytz
import os


def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///questions.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()  # Create database tables within the application context

    @app.route('/', methods=['GET'])
    def index():
        print("Get index.html")
        return render_template('index.html')

    @app.route('/submit', methods=['POST'])
    def submit_question():
        print("Submit Questions")
        question_text = request.form.get('question')
        response_text = request.form.get('response')
        category = request.form.get('category')  # Retrieve the selected category
        subtags_str = request.form.get('subtags')  # Retrieve the subtags string
    
        # Process the subtags string
        subtags_list = [tag.strip() for tag in subtags_str.split(',') if tag.strip()]

        # Create the new question
        new_question = Question(question_text=question_text, response_text=response_text, category=category)

        # Associate subtags with the new question
        for tag_name in subtags_list:
            subtag = Subtag.query.filter_by(name=tag_name).first()
            if not subtag:
                # Create a new subtag if it doesn't exist
                subtag = Subtag(name=tag_name)
                db.session.add(subtag)
            new_question.subtags.append(subtag)
            db.session.add(new_question)
            db.session.commit()

        # return redirect(url_for('index'))
        return jsonify({'message': 'Question and response saved successfully!'})
    
    @app.route('/get-info')
    def get_info():
        # Fetch the most recent 10 questions, ordered by creation time
        recent_questions = Question.query.order_by(Question.created_at.desc()).limit(10).all()

        info_html = ''
        for question in recent_questions:
            # Format each question as HTML, including category and subtags
            info_html += f'<div>'
            info_html += f'<p><strong>Category:</strong> {question.category}</p>'
            info_html += f'<p><strong>Question:</strong> {question.question_text}</p>'
            info_html += f'<p><strong>Response:</strong> {question.response_text}</p>'

            # Handle subtags - assuming subtags is a list of Subtag objects
            subtags_str = ', '.join([subtag.name for subtag in question.subtags])
            info_html += f'<p><strong>Subtags:</strong> {subtags_str}</p>'

            info_html += f'<p><strong>Asked on:</strong> {question.created_at.strftime("%Y-%m-%d %H:%M:%S")}</p>'
            info_html += f'</div><hr>'

        return {'info': info_html}  # Return the information as HTML
        
    @app.route('/generate-pdf')
    def generate_pdf():
        pdf_dir = "pdfs"
        if not os.path.exists(pdf_dir):
            os.makedirs(pdf_dir)

        # Generate a timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Interview_review_{timestamp}.pdf"
        pdf_path = os.path.join(pdf_dir, filename)

        doc = MyDocTemplate(pdf_path)
        
        # Define a bold style for questions
        styles = getSampleStyleSheet()
        questionStyle = ParagraphStyle('QuestionStyle', parent=styles['Normal'], fontName='Helvetica-Bold')
        heading1_style = styles['Heading1']
        heading2_style = styles['Heading2']
        flowables = []

        # Fetch categories and subtags from the database and add them to the PDF
        categories = Question.query.with_entities(Question.category).distinct()
        for category_tuple in categories:
            category = category_tuple[0]  # Extract category name from the tuple
            flowables.append(Paragraph(category, heading1_style))
            flowables.append(Spacer(1, 12))  # Add some space after the category

            subtags = Subtag.query.join(Question.subtags).filter(Question.category == category).distinct()

            for subtag in subtags:
                flowables.append(Paragraph(subtag.name, heading2_style))
                flowables.append(Spacer(1, 12))  # Add some space after the subtag

                questions = Question.query.join(Question.subtags).filter(Question.category == category, Subtag.id == subtag.id).all()
                # Initialize a counter for numbering questions within each subtag section
                question_counter = 1
                for question in questions:
                    # Format and add the question text with numbering
                    question_text = f"Question {question_counter}: {question.question_text}"
                    flowables.append(Paragraph(question_text, questionStyle))
                    
                    # Format and add the response text
                    response_text = f"Answer: {question.response_text}"
                    flowables.append(Paragraph(response_text, styles['Normal']))

                    # Add some space after each question and response pair
                    flowables.append(Spacer(1, 12))

                    # Increment the question counter
                    question_counter += 1
        doc.build(flowables)  # Build the PDF

        # Send the generated PDF file to the client
        directory = os.path.dirname(pdf_path)
        filename = os.path.basename(pdf_path)
        return send_from_directory(directory=directory, path=filename, as_attachment=True)

    return app

# Initialize SQLAlchemy outside of create_app
db = SQLAlchemy()

# Define your models
class Subtag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

subtags_questions = db.Table('subtags_questions',
    db.Column('subtag_id', db.Integer, db.ForeignKey('subtag.id'), primary_key=True),
    db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True)
)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(500), nullable=False)
    response_text = db.Column(db.String(2000), nullable=True)
    category = db.Column(db.String(100), nullable=False)  # Simple string field for category
    # Assuming a relationship is set up for subtags
    subtags = db.relationship('Subtag', secondary=subtags_questions, lazy='subquery',
                              backref=db.backref('questions', lazy=True))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('America/Los_Angeles')))

class MyDocTemplate(BaseDocTemplate):
    def __init__(self, *args, **kwargs):
        BaseDocTemplate.__init__(self, *args, **kwargs)
        # Calculate the available height for the Frame
        frame_height = self.height - self.topMargin - self.bottomMargin
        frame_width = self.width - self.leftMargin - self.rightMargin
        frame = Frame(self.leftMargin, self.bottomMargin, frame_width, frame_height, id='normal')
        template = PageTemplate(id='OneCol', frames=frame)
        self.addPageTemplates([template])
    
    def on_my_page(self, canvas, doc):
        canvas.saveState()
        # Here you can do other canvas drawings for each page
        canvas.restoreState()

    def afterFlowable(self, flowable):
        "Registers TOC entries and adds bookmarks."
        if isinstance(flowable, Paragraph):
            text = flowable.getPlainText()
            styleName = flowable.style.name
            if 'Heading' in styleName:  # For category and subtag headings
                level = int(styleName[-1])
                self._add_bookmark(text, level)
            elif styleName == 'QuestionStyle':  # For questions
                # Adjust the level for questions, if necessary
                self._add_bookmark(f"{text}", 3)  # Example: level 2 for questions
    
    def _add_bookmark(self, text, level):
        key = str(hash(text))  # Unique key for the bookmark
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level-1, closed=False)



# Create the Flask app instance
app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
