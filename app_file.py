import streamlit as st
import pymupdf
import re
import google.generativeai as genai
import ebooklib
from ebooklib import epub
from io import BytesIO
import os
import tempfile
from bs4 import BeautifulSoup

default_prompt = """
# Mission

You are a learning, teaching and analysis bot that extracts key ideas, concepts, and actionable frameworks or methodologies from text files.

# Context

The context involves the summarization of text files for the purposes of practical education, focusing on the key ideas, concepts, and actionable frameworks or methodologies. You are expected to be comprehensive, accurate, and concise.

# Rules

Please read through the text carefully. Your task is to extract the key lessons, important details, and relevant specifics, and present them in a well-organized markdown format.

Look specifically for:
- ⁠  ⁠Key concepts, theories, mental models, frameworks, methods and ideas
- ⁠  ⁠Illuminating anecdotes, examples or stories that illustrate the main points
- ⁠  ⁠Specific action items, exercises, or how-to steps the reader can take
- ⁠  ⁠Relevant details that add depth and context to the key lessons

# Expected Input

You will receive the full text from the file.

<file_text>
{file_text}
</file_text>

# Output Format

1.⁠ ⁠Overview:
   - Provide a high-level executive summary of the text.

2.⁠ ⁠Key Topics and Lessons:
   - List the key topics and lessons covered in the text with brief descriptions.

3.⁠ ⁠Key Lessons/Topics Details:
   - Concepts, Theory, Mental Models, Frameworks, Methods, Ideas, and Required Background Knowledge:
     - Describe the main concepts, theories, mental models, frameworks, methods, and ideas introduced in the text.
     - Include any necessary background knowledge required to understand these elements.
  
   - Specific Anecdotes or Stories:
     - Summarize any specific anecdotes or stories mentioned in the text that illustrate the key points.

   - Action Items, Key Takeaways, and How-to's:
     - List actionable items and key takeaways from the text.
     - Provide step-by-step instructions or guidance on how to implement the advice or lessons from the text.

IMPORTANT!!! Output your response within <markdown></markdown> tags.

---

Example Format:

<markdown>

Overview:
Provide a high-level executive summary of the text.

Key Topics and Lessons:
- ⁠ ⁠Topic 1: Brief description
- ⁠  ⁠Topic 2: Brief description
- ⁠  ⁠...

Key Lessons/Topics Details:

- ⁠  ⁠Concepts, Theory, Mental Models, Frameworks, Methods, Ideas, and Required Background Knowledge:
  - Concept 1: Description
  - Theory 1: Description
  - Mental Model 1: Description
  - Framework 1: Description
  - ...

- ⁠  ⁠Specific Anecdotes or Stories:
  - Anecdote 1: Short summary
  - Anecdote 2: Short summary
  - ...

- ⁠  ⁠Action Items, Key Takeaways, and How-to's:
  - Action Item 1: Step-by-step instructions
  - Action Item 2: Step-by-step instructions
  - …

</markdown>
"""

# Function to get key ideas using Google Gemini API
def get_key_ideas(file_text, api_key, prompt):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro')
    prompt = prompt.replace("{file_text}", file_text)
    try:
        response = model.generate_content(prompt)
        print(response)
        result = response.candidates[0].content.parts[0].text
        # Extract content between <markdown> tags using regex
        match = re.search(r'<markdown>(.*)', result, re.IGNORECASE | re.DOTALL)
        if match:
            key_ideas = match.group(1).strip()
            # Remove block quote formatting
            key_ideas = re.sub(r'^\s*>\s*', '', key_ideas, flags=re.MULTILINE)
        else:
            key_ideas = None
        
        return key_ideas
    except Exception as e:
        st.error(f"Error in Gemini API call: {str(e)}")
        return None

# Caching function to process file and extract text
@st.cache_data
def process_file(file_content, file_type):
    try:
        if file_type == "application/pdf":
            # Process PDF file
            with BytesIO(file_content) as file:
                doc = pymupdf.open(stream=file, filetype="pdf")
                full_text = ""
                for page in doc:
                    full_text += page.get_text()
        elif file_type == "application/epub+zip":
            # Process epub file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            book = epub.read_epub(temp_file_path)
            full_text = ""

            for item in book.get_items():
                if isinstance(item, ebooklib.epub.EpubHtml):
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    full_text += soup.get_text()

            os.unlink(temp_file_path)  # Clean up the temporary file
        else:
            # Process txt file
            full_text = file_content.decode("utf-8")
        
        return full_text
    except Exception as e:
        st.error(f"An error occurred: {e}")
        return None

# Initialize session state variables
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''

if 'uploaded_file_content' not in st.session_state:
    st.session_state['uploaded_file_content'] = None

if 'custom_prompt' not in st.session_state:
    st.session_state['custom_prompt'] = default_prompt

# Streamlit app
st.title("Lesson Extractor")

# Sidebar selection
page = st.sidebar.radio("Select Page", ("Home", "Prompt"))

if page == "Home":
    # Sidebar for file upload
    uploaded_file = st.sidebar.file_uploader("Upload a PDF, TXT, or EPUB file", type=["pdf", "txt", "epub"])
    if uploaded_file is not None:
        # Store the uploaded file content in session state
        st.session_state['uploaded_file_content'] = uploaded_file.read()
        st.session_state['file_type'] = uploaded_file.type

    # Sidebar for API key input at the bottom
    st.session_state['api_key'] = st.sidebar.text_input("Enter your Google Gemini API key", value=st.session_state['api_key'])

    if st.session_state['uploaded_file_content']:
        # Display the entire book text
        raw_text_placeholder = st.empty()

        full_text = process_file(st.session_state['uploaded_file_content'], st.session_state['file_type'])
        raw_text_placeholder.write(full_text)
        
        # Extract button
        if st.sidebar.button("Extract Lessons"):
            # Clear the raw text and show extracting message
            raw_text_placeholder.empty()
            extracting_message = st.warning("Extracting key lessons...")

            # Get key ideas from the entire book text
            key_ideas = get_key_ideas(full_text, st.session_state['api_key'], st.session_state['custom_prompt'])

            # Show success message and display key ideas
            extracting_message.empty()
            if key_ideas is None:
                st.error("Could not extract the lessons.")
            else:
                st.success("Key lessons extracted!")
                st.markdown(key_ideas)
    else:
        st.write("Please upload a PDF, TXT, or EPUB file using the sidebar.")

elif page == "Prompt":
    st.markdown('<span style="color:yellow;">**WARNING:** You NEED to mention &lt;file_text&gt;&lt;/file_text&gt; and &lt;markdown&gt;&lt;/markdown&gt; tags in the prompt. Make sure to press Save to apply changes', unsafe_allow_html=True)
    prompt = st.text_area("Edit the prompt below:", value=st.session_state['custom_prompt'], height=400)
    
    if st.button("Save"):
        st.session_state['custom_prompt'] = prompt
        st.success("Prompt saved!")