import os
import uuid
import json
import threading
import time
from flask import Flask, request, jsonify
import google.generativeai as genai_text
from google import genai

app = Flask(__name__, static_folder='static', static_url_path='/')

genai_text.configure(api_key=os.environ.get("GEMINI_API_KEY"))
research_agent = genai_text.GenerativeModel('gemini-2.5-flash')

video_jobs = {}

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_location():
    data = request.json
    image_data = data.get('image')
    
    if not image_data:
        return jsonify({'error': 'No image provided'}), 400

    image_data = image_data.split(",")[1]
    
    # Updated Prompt: Now requests 'era' and 'visual_scene' for nearby places too!
    prompt = """
    Analyze this image. 
    1. Identify the monument or location and provide its exact latitude and longitude.
    2. Provide a strict 1-sentence (max 20 words) historical tour guide script suitable for a 10-second video.
    3. Identify the specific 'era' it was built (e.g., "Ancient Egypt, 2560 BC", "Mughal Empire, 1632").
    4. Provide a 'visual_scene' describing what a bustling day looked like there when it was newly built (e.g., "Merchants trading in colorful tents while workers carve limestone").
    5. List 3 nearby attractions. For EACH, provide the name, latitude, longitude, a brief 1-sentence description, the 'era' it was built, and a 'visual_scene' of it in its prime.
    
    You MUST format your response as strict JSON without markdown formatting like this:
    {
      "location": "Name",
      "lat": 0.0,
      "lng": 0.0,
      "script": "...",
      "era": "...",
      "visual_scene": "...",
      "nearby": [
        {"name": "...", "lat": 0.0, "lng": 0.0, "description": "...", "era": "...", "visual_scene": "..."}
      ]
    }
    """
    
    try:
        response = research_agent.generate_content([
            {'mime_type': 'image/jpeg', 'data': image_data},
            prompt
        ])
        
        clean_text = response.text.strip().removeprefix('```json').removesuffix('```')
        result = json.loads(clean_text)
        return jsonify(result)
    except Exception as e:
        print(f"Agent 1 Error: {e}")
        return jsonify({'error': 'Failed to analyze image.'}), 500

@app.route('/api/generate-video', methods=['POST'])
def generate_video():
    data = request.json
    location = data.get('location')
    era = data.get('era')
    visual_scene = data.get('visual_scene')
    
    job_id = str(uuid.uuid4())
    video_jobs[job_id] = {'status': 'processing', 'url': None}
    
    veo_prompt = (
        f"Cinematic historical recreation, set exactly in the era of {era}. "
        f"The monument {location} is newly built and coming alive. {visual_scene}. "
        f"Hyper-realistic, atmospheric lighting, dust motes, bustling ancient life, "
        f"historical archive documentary style brought to vivid life, 8k resolution, smooth panning, masterpiece."
    )
    
    def background_generate(prompt_text, j_id):
        try:
            client = genai.Client()
            operation = client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt=prompt_text,
            )
            
            while not operation.done:
                time.sleep(10)
                operation = client.operations.get(operation)
                
            generated_video = operation.response.generated_videos[0]
            
            videos_dir = os.path.join(app.static_folder, 'videos')
            os.makedirs(videos_dir, exist_ok=True)
            
            filename = f"{j_id}.mp4"
            filepath = os.path.join(videos_dir, filename)
            
            client.files.download(file=generated_video.video)
            generated_video.video.save(filepath)
            
            video_jobs[j_id]['url'] = f"/videos/{filename}"
            video_jobs[j_id]['status'] = 'done'
            
        except Exception as e:
            video_jobs[j_id]['status'] = 'failed'
            print(f"Veo Error: {e}")

    threading.Thread(target=background_generate, args=(veo_prompt, job_id)).start()

    return jsonify({
        'status': 'processing', 
        'message': 'Video generation started.',
        'job_id': job_id 
    })

@app.route('/api/video-status/<job_id>', methods=['GET'])
def check_video_status(job_id):
    job = video_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(job)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)