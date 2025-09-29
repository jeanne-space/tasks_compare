# DB 테이블 구조 비교 봇

월요일과 금요일 그룹의 데이터베이스 테이블 스크린샷을 업로드하고 Claude AI를 통해 테이블 구조 차이점을 분석하는 웹 애플리케이션입니다.

## 기능

- 📁 **DB 스크린샷 업로드**: 월요일/금요일 그룹별로 테이블 스크린샷 업로드
- 🔍 **AI 분석**: Claude AI를 통한 테이블 구조 비교 분석
- 📊 **구조적 차이점**: 테이블 존재 여부, 컬럼 구조 변경사항 등 정확한 분석
- 🗑️ **그룹 관리**: 각 그룹별 이미지 초기화 기능

## 설치 및 실행

### 1. 의존성 설치
```bash
cd image-compare-bot
pip install -r requirements.txt
```

### 2. 환경 변수 설정
`.env` 파일을 생성하고 Anthropic API 키를 설정합니다:
```bash
cp .env.example .env
# .env 파일에서 ANTHROPIC_API_KEY를 실제 키로 변경
```

### 3. 애플리케이션 실행
```bash
python app.py
```

### 4. 웹 브라우저에서 접속
http://localhost:5000 에 접속하여 애플리케이션을 사용합니다.

## 사용 방법

1. **DB 스크린샷 업로드**
   - 월요일 그룹에 데이터베이스 테이블 스크린샷 3-4개 업로드
   - 금요일 그룹에 데이터베이스 테이블 스크린샷 3-4개 업로드

2. **분석 실행**
   - "🔍 테이블 구조 비교 분석 시작" 버튼 클릭
   - Claude AI가 테이블 구조를 분석할 때까지 대기

3. **결과 확인**
   - 월요일에만 존재하는 테이블
   - 금요일에만 존재하는 테이블  
   - 구조가 변경된 테이블의 컬럼 차이점
   - 동일하게 존재하는 테이블 목록

## 지원하는 이미지 형식

- PNG
- JPG/JPEG
- GIF
- BMP
- WEBP

## API 키 획득

Anthropic Claude API 키는 [Anthropic Console](https://console.anthropic.com/)에서 획득할 수 있습니다.

## 기술 스택

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **AI**: Anthropic Claude API
- **이미지 처리**: Pillow (PIL)