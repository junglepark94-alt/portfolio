# 포트폴리오 사이트 — Flask

## 로컬 실행

```bash
# 1. 가상환경 생성
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 실행
python wsgi.py
```

브라우저에서 http://localhost:8080 접속  
관리자 페이지: http://localhost:8080/admin/login  
기본 계정: admin / changeme123!

---

## Railway 배포

### 1. GitHub 연결
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_ID/portfolio.git
git push -u origin main
```

### 2. Railway 프로젝트 생성
1. https://railway.app 접속 → New Project
2. Deploy from GitHub repo 선택
3. 저장소 연결 → 자동 배포 시작

### 3. 환경 변수 설정 (Railway > Variables)

| 키 | 값 |
|---|---|
| `SECRET_KEY` | (무작위 긴 문자열, 예: `openssl rand -hex 32` 결과) |
| `ADMIN_PASSWORD` | 관리자 비밀번호 (변경 필수!) |

> Railway는 `PORT` 환경 변수를 자동 주입합니다.  
> `DATABASE_URL`을 설정하지 않으면 SQLite가 사용됩니다.  
> Railway Volume을 연결하면 SQLite 데이터가 유지됩니다.

### 4. 커스텀 도메인 (선택)
Railway > Settings > Domains → 무료 `.up.railway.app` 도메인 제공

---

## 개인정보 수정

`templates/index.html` 에서 아래 항목을 찾아 수정:

- `[이름]` → 본인 이름
- `your@email.com` → 이메일
- LinkedIn / GitHub URL
- 경력 사항, 핵심 역량

프로젝트는 관리자 페이지(`/admin`)에서 추가/수정/삭제 가능합니다.
