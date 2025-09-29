import os
import base64
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import anthropic
from dotenv import load_dotenv
# from PIL import Image  # Removed to avoid deployment issues
from notion_client import Client
from datetime import datetime, timedelta
import json

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

# Anthropic 클라이언트를 초기화합니다.
# 'proxies' 인자는 현재 버전의 Anthropic 라이브러리에서 지원되지 않으므로 제거합니다.
# API 키는 환경 변수 'ANTHROPIC_API_KEY'에서 자동으로 로드됩니다.
try:
    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
    )
    
    # 선택 사항: API 키가 제대로 설정되었는지 확인하는 로직입니다.
    if client.api_key is None:
        print("Warning: ANTHROPIC_API_KEY environment variable is not set.")
        client = None
    else:
        print("Anthropic client initialized successfully")
        
except Exception as e:
    print(f"Anthropic client initialization error: {e}")
    client = None

try:
    notion = Client(auth=os.getenv('NOTION_TOKEN'))
    notion_db_id = os.getenv('NOTION_DATABASE_ID')
except Exception as e:
    print(f"Notion client initialization error: {e}")
    notion = None
    notion_db_id = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_image_type(image_path):
    # Simple file extension based detection
    ext = os.path.splitext(image_path)[1].lower()
    ext_map = {
        '.jpg': 'jpeg',
        '.jpeg': 'jpeg', 
        '.png': 'png',
        '.gif': 'gif',
        '.bmp': 'bmp',
        '.webp': 'webp'
    }
    return ext_map.get(ext, 'jpeg')

def get_uploaded_images(group):
    folder_path = os.path.join(app.config['UPLOAD_FOLDER'], group)
    if not os.path.exists(folder_path):
        return []
    return [f for f in os.listdir(folder_path) if allowed_file(f)]

@app.route('/health')
def health():
    return {'status': 'healthy', 'message': 'Service is running'}, 200

@app.route('/debug')
def debug():
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    notion_token = os.getenv('NOTION_TOKEN')
    notion_db_id = os.getenv('NOTION_DATABASE_ID')
    flask_env = os.getenv('FLASK_ENV')
    
    return {
        'anthropic_key_exists': bool(anthropic_key),
        'anthropic_key_length': len(anthropic_key) if anthropic_key else 0,
        'anthropic_key_starts_with': anthropic_key[:10] if anthropic_key else 'None',
        'notion_token_exists': bool(notion_token),
        'notion_db_id_exists': bool(notion_db_id),
        'flask_env': flask_env,
        'client_initialized': client is not None
    }

@app.route('/')
def index():
    monday_images = get_uploaded_images('monday')
    friday_images = get_uploaded_images('friday')
    return render_template('index.html', 
                         monday_images=monday_images, 
                         friday_images=friday_images)

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        print(f"업로드 요청 받음: {request.files}, {request.form}")
        
        if 'file' not in request.files:
            print("파일이 요청에 없음")
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
        
        file = request.files['file']
        group = request.form.get('group')
        
        print(f"파일명: {file.filename}, 그룹: {group}")
        
        if file.filename == '':
            print("파일명이 비어있음")
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
        
        if group not in ['monday', 'friday']:
            print(f"잘못된 그룹: {group}")
            return jsonify({'error': '올바르지 않은 그룹입니다.'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            group_folder = os.path.join(app.config['UPLOAD_FOLDER'], group)
            os.makedirs(group_folder, exist_ok=True)
            
            filepath = os.path.join(group_folder, filename)
            print(f"파일 저장 경로: {filepath}")
            
            file.save(filepath)
            print(f"파일 저장 완료: {filepath}")
            
            return jsonify({'success': True, 'message': f'{group} 그룹에 이미지가 업로드되었습니다.'})
        
        print(f"허용되지 않는 파일 형식: {file.filename}")
        return jsonify({'error': '허용되지 않는 파일 형식입니다.'}), 400
        
    except Exception as e:
        print(f"업로드 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'업로드 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/compare', methods=['POST'])
def compare_images():
    if client is None:
        return jsonify({'error': 'Anthropic 클라이언트가 초기화되지 않았습니다. 환경변수를 확인해주세요.'}), 500
        
    monday_images = get_uploaded_images('monday')
    friday_images = get_uploaded_images('friday')
    
    if len(monday_images) == 0 or len(friday_images) == 0:
        return jsonify({'error': '월요일과 금요일 그룹 모두에 최소 1개의 이미지가 필요합니다.'}), 400
    
    try:
        content_parts = []
        
        content_parts.append({
            "type": "text",
            "text": f"다음 이미지들을 분석해주세요.\n\n월요일 그룹 ({len(monday_images)}개 이미지):"
        })
        
        for i, img in enumerate(monday_images):
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], 'monday', img)
            img_type = get_image_type(img_path)
            img_data = encode_image_to_base64(img_path)
            content_parts.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f"image/{img_type}",
                    "data": img_data
                }
            })
        
        content_parts.append({
            "type": "text",
            "text": f"\n금요일 그룹 ({len(friday_images)}개 이미지):"
        })
        
        for i, img in enumerate(friday_images):
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], 'friday', img)
            img_type = get_image_type(img_path)
            img_data = encode_image_to_base64(img_path)
            content_parts.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f"image/{img_type}",
                    "data": img_data
                }
            })
        
        content_parts.append({
            "type": "text",
            "text": """

위의 월요일과 금요일 이미지들은 업무 목록 스크린샷입니다. 두 그룹을 비교하여 다음과 같이 분석해주세요:

1. **월요일에만 존재하는 업무들**: 
   - 업무 제목과 진행상태 (퍼센트만 표시)

2. **금요일에만 존재하는 업무들**: 
   - 업무 제목과 진행상태 (퍼센트만 표시)

3. **두 날짜 모두 존재하지만 상태가 변경된 업무들**: 
   - 업무 제목과 구체적인 변경사항 (진행률, 상태 등)

4. **두 날짜 모두 동일한 상태로 존재하는 업무들**: 
   - 업무 제목 목록

**중요한 지시사항:**
- 진행률을 표시할 때 "진행중"이라는 단어는 절대 사용하지 말고, 퍼센트(%)만 표시해주세요.
- 예: "(30% 진행중)" → "(30%)"
- 각 항목별로 정확한 업무명과 상태를 명시해서 답변해주세요. 
- 디자인이나 색상 등은 분석에서 제외하고 순수하게 업무 내용과 진행상태 차이만 분석해주세요.
"""
        })
        
        # 실제 이미지 분석 기능 복원
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": content_parts
            }]
        )
        
        analysis_result = response.content[0].text
        
        return jsonify({
            'success': True,
            'analysis': analysis_result,
            'monday_count': len(monday_images),
            'friday_count': len(friday_images),
            'monday_images': [{'filename': img, 'path': f'/uploads/monday/{img}'} for img in monday_images],
            'friday_images': [{'filename': img, 'path': f'/uploads/friday/{img}'} for img in friday_images]
        })
        
    except Exception as e:
        print(f"분석 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'분석 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/clear/<group>')
def clear_group(group):
    if group not in ['monday', 'friday']:
        return jsonify({'error': '올바르지 않은 그룹입니다.'}), 400
    
    group_folder = os.path.join(app.config['UPLOAD_FOLDER'], group)
    if os.path.exists(group_folder):
        for filename in os.listdir(group_folder):
            file_path = os.path.join(group_folder, filename)
            if os.path.isfile(file_path):
                os.unlink(file_path)
    
    return jsonify({'success': True, 'message': f'{group} 그룹의 모든 이미지가 삭제되었습니다.'})

@app.route('/uploads/<group>/<filename>')
def uploaded_file(group, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], group), filename)

def get_notion_data_by_date(start_date, end_date):
    """특정 날짜 범위의 노션 데이터를 가져오는 함수"""
    try:
        # 날짜 필터를 사용하여 데이터 조회
        filter_query = {
            "and": [
                {
                    "property": "발제일",
                    "date": {
                        "on_or_after": start_date
                    }
                },
                {
                    "property": "발제일", 
                    "date": {
                        "on_or_before": end_date
                    }
                }
            ]
        }
        
        response = notion.databases.query(
            database_id=notion_db_id,
            filter=filter_query,
            page_size=100
        )
        
        tasks = []
        for page in response.get('results', []):
            properties = page.get('properties', {})
            
            # 각 속성값 추출
            title = ""
            if properties.get('업무티켓명', {}).get('title'):
                title = ''.join([t.get('plain_text', '') for t in properties['업무티켓명']['title']])
            
            status = ""
            if properties.get('상태', {}).get('select'):
                status = properties['상태']['select'].get('name', '')
            
            progress = 0
            if properties.get('진행률', {}).get('number') is not None:
                progress = properties['진행률']['number']
            
            priority = []
            if properties.get('우선순위', {}).get('multi_select'):
                priority = [p.get('name', '') for p in properties['우선순위']['multi_select']]
            
            category = []
            if properties.get('세부범주', {}).get('multi_select'):
                category = [c.get('name', '') for c in properties['세부범주']['multi_select']]
            
            start_date_str = ""
            if properties.get('발제일', {}).get('date'):
                start_date_str = properties['발제일']['date'].get('start', '')
            
            deadline_str = ""
            if properties.get('목표기한', {}).get('date'):
                deadline_str = properties['목표기한']['date'].get('start', '')
            
            tasks.append({
                'title': title,
                'status': status,
                'progress': progress,
                'priority': priority,
                'category': category,
                'start_date': start_date_str,
                'deadline': deadline_str,
                'id': page.get('id', '')
            })
        
        return tasks
    except Exception as e:
        print(f"노션 데이터 조회 오류: {e}")
        return []

def analyze_notion_data(monday_date, friday_date):
    """월요일과 금요일 데이터를 분석하는 함수"""
    monday_data = get_notion_data_by_date(monday_date, monday_date)
    friday_data = get_notion_data_by_date(friday_date, friday_date)
    
    analysis = {
        'monday_tasks': len(monday_data),
        'friday_tasks': len(friday_data),
        'status_comparison': {},
        'progress_changes': [],
        'priority_distribution': {},
        'category_distribution': {}
    }
    
    # 상태별 분석
    monday_status = {}
    friday_status = {}
    
    for task in monday_data:
        status = task['status']
        monday_status[status] = monday_status.get(status, 0) + 1
    
    for task in friday_data:
        status = task['status']
        friday_status[status] = friday_status.get(status, 0) + 1
    
    # 모든 상태 목록
    all_statuses = set(monday_status.keys()) | set(friday_status.keys())
    for status in all_statuses:
        analysis['status_comparison'][status] = {
            'monday': monday_status.get(status, 0),
            'friday': friday_status.get(status, 0)
        }
    
    # 우선순위 분포 (금요일 기준)
    for task in friday_data:
        for priority in task['priority']:
            analysis['priority_distribution'][priority] = analysis['priority_distribution'].get(priority, 0) + 1
    
    # 카테고리 분포 (금요일 기준)
    for task in friday_data:
        for category in task['category']:
            analysis['category_distribution'][category] = analysis['category_distribution'].get(category, 0) + 1
    
    return analysis

@app.route('/notion-analysis', methods=['POST'])
def notion_analysis():
    """노션 DB 분석 엔드포인트"""
    try:
        data = request.get_json()
        monday_date = data.get('monday_date')
        friday_date = data.get('friday_date')
        
        if not monday_date or not friday_date:
            return jsonify({'error': '월요일과 금요일 날짜가 모두 필요합니다.'}), 400
        
        analysis_result = analyze_notion_data(monday_date, friday_date)
        
        return jsonify({
            'success': True,
            'analysis': analysis_result,
            'monday_date': monday_date,
            'friday_date': friday_date
        })
        
    except Exception as e:
        print(f"노션 분석 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'노션 분석 중 오류가 발생했습니다: {str(e)}'}), 500

# 앱 시작 시 디렉터리 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'monday'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'friday'), exist_ok=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')