import os
import signal
import sys
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import threading
import time
import gc
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

resume = """Thanush is a Python Developer with 1 years of experience in building and optimizing scalable applications.
He specializes in developing backend solutions, integrating RESTful APIs, and managing databases efficiently.
His expertise includes working with frameworks like Django and Flask, implementing security best practices, and optimizing application performance.
He has a strong understanding of cloud platforms, DevOps tools, and containerization, enabling seamless deployment and automation.
Thanush is adept at troubleshooting complex issues and collaborating with cross-functional teams to deliver high-quality software solutions."""

job_description= """Data Analyst: Extract, analyze, and interpret data to drive business insights.
                    Create visualizations and reports to communicate findings and support strategic decision-making."""

app = Flask(__name__)
# Enable CORS for all domains
CORS(app, resources={r"/*": {"origins": "*"}})
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['STATIC_FOLDER'] = 'static'

# Store active interviews in memory (note: this will reset on serverless function cold starts)
active_threads = {}

class Interview:
    def __init__(self, agent_id, api_key, resume, job_description):
        self.agent_id = agent_id
        self.api_key = api_key
        self.resume = resume
        self.job_description = job_description
        self.running = True
        self.question_count = 0
        self.max_questions = 7
        self.conversation = None
        self.thread = None
        logger.info(f"Initialized interview for agent_id: {agent_id}")

    def run(self):
        try:
            logger.info(f"Starting interview for agent_id: {self.agent_id}")
            dynamic_vars = {
                "resume": self.resume,
                "job_description": self.job_description,
                "agent_id": self.agent_id
            }
            config = ConversationInitiationData(
                dynamic_variables=dynamic_vars
            )

            client = ElevenLabs(api_key=self.api_key)
            self.conversation = Conversation(
                client,
                self.agent_id,
                config=config,
                requires_auth=bool(self.api_key),
                audio_interface=DefaultAudioInterface(),
                callback_agent_response=self.handle_agent_response,
                callback_user_transcript=lambda transcript: logger.info(f"User: {transcript}"),
            )
            
            logger.info(f"Starting conversation session for agent_id: {self.agent_id}")
            self.conversation.start_session()
            
            while self.running and self.question_count < self.max_questions:
                time.sleep(0.1)
            
            if self.question_count >= self.max_questions:
                logger.info(f"Interview completed for agent_id: {self.agent_id}")
                print("Agent: Thank you for your time! This concludes our interview. We will review your responses and get back to you soon.")
                self.conversation.end_session()
                print("Interview ended after 7 questions")
            else:
                logger.info(f"Interview cancelled for agent_id: {self.agent_id}")
                self.conversation.end_session()
        except Exception as e:
            logger.error(f"Error in interview for agent_id {self.agent_id}: {str(e)}")
            print(f"Error in interview: {e}")
        finally:
            # Cleanup
            if self.conversation:
                try:
                    self.conversation.end_session()
                except Exception as e:
                    logger.error(f"Error ending session for agent_id {self.agent_id}: {str(e)}")
            if self.agent_id in active_threads:
                del active_threads[self.agent_id]
            gc.collect()  # Force garbage collection
            logger.info(f"Cleaned up interview for agent_id: {self.agent_id}")

    def handle_agent_response(self, response):
        logger.info(f"Agent {self.agent_id}: {response}")
        print(f"Agent: {response}")
        self.question_count += 1
        if self.question_count >= self.max_questions:
            self.running = False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/offer', methods=['POST'])
def handle_offer():
    try:
        data = request.json
        logger.info("Received request data: %s", data)
        logger.info("Request headers: %s", dict(request.headers))
        
        if not data:
            logger.error("No JSON data received")
            return jsonify({'error': 'No JSON data received'}), 400
            
        agent_id = data.get('agentId')
        api_key = data.get('apiKey')
        resume = data.get('resume')
        job_description = data.get('jobDescription')
        
        logger.info("Extracted values: agent_id=%s, resume_length=%d, job_description_length=%d",
                   agent_id, len(resume) if resume else 0, len(job_description) if job_description else 0)
        
        if not agent_id:
            logger.error("Missing agentId")
            return jsonify({'error': 'Agent ID is required'}), 400
        if not api_key:
            logger.error("Missing apiKey")
            return jsonify({'error': 'API Key is required'}), 400
        if not resume:
            logger.error("Missing resume")
            return jsonify({'error': 'Resume is required'}), 400
        if not job_description:
            logger.error("Missing jobDescription")
            return jsonify({'error': 'Job Description is required'}), 400
        
        # Cleanup any existing interview for this agent
        if agent_id in active_threads:
            logger.info(f"Cleaning up existing interview for agent_id: {agent_id}")
            old_interview = active_threads[agent_id]
            old_interview.running = False
            del active_threads[agent_id]
            gc.collect()
        
        # Create and start interview
        interview = Interview(agent_id, api_key, resume, job_description)
        thread = threading.Thread(target=interview.run)
        interview.thread = thread
        active_threads[agent_id] = interview
        thread.start()
        
        logger.info(f"Started new interview for agent_id: {agent_id}")
        return jsonify({'conversationId': agent_id})
    except Exception as e:
        logger.error("Error in handle_offer: %s", str(e))
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/cancel', methods=['POST'])
def handle_cancel():
    try:
        data = request.json
        agent_id = data.get('agentId')
        logger.info(f"Received cancel request for agent_id: {agent_id}")
        
        if not agent_id:
            logger.error("Missing agentId in cancel request")
            return jsonify({'error': 'Agent ID is required'}), 400
        
        if agent_id in active_threads:
            logger.info(f"Cancelling interview for agent_id: {agent_id}")
            interview = active_threads[agent_id]
            interview.running = False
            del active_threads[agent_id]
            return jsonify({'status': 'cancelled'})
        
        logger.warning(f"No active session found for agent_id: {agent_id}")
        return jsonify({'error': 'No active session found'}), 404
    except Exception as e:
        logger.error("Error in handle_cancel: %s", str(e))
        return jsonify({'error': f'Server error: {str(e)}'}), 500

# For local development
if __name__ == '__main__':
    # Run on all interfaces (0.0.0.0) on port 8080
    app.run(host='0.0.0.0', port=8080, debug=False)