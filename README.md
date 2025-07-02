# 🖨️ POS 프린터 프로그램

Supabase와 연동하여 주문 데이터를 자동으로 프린터에서 출력하는 Windows용 프로그램입니다.

## 🚀 간편 설치 (비개발자용)

### 1. 프로그램 다운로드
- [최신 릴리즈](../../releases/latest)에서 `POS_Printer_vX.X.X.zip` 다운로드
- 바탕화면에 압축 해제

### 2. 원클릭 설치
**🥇 방법 1 (추천)**: **`간편설치.bat`** 더블클릭 → UAC에서 "예" 클릭  
**🥈 방법 2**: **`build.ps1`** 우클릭 → "PowerShell로 실행" → UAC에서 "예" 클릭

자동으로 모든 것이 설치됩니다! ☕ 커피 한 잔 하고 오세요 (10-20분 소요)

### 3. 프로그램 실행
1. 빌드 완료 후 **`POS_Printer_Release`** 폴더 생성됨
2. 해당 폴더에서 **`설치.ps1`** 우클릭 → **"PowerShell로 실행"**
3. 바탕화면에 **"POS 프린터"** 바로가기 생성
4. 바로가기 더블클릭으로 프로그램 실행! 🎉

> **📖 자세한 설치 방법**: [설치 가이드](INSTALLATION_GUIDE.md) 참조

## 📋 시스템 요구사항

- **Windows 10 이상**
- **4GB RAM 이상**
- **2GB 여유 공간** (빌드 과정에서 필요)
- **인터넷 연결** (Python 및 패키지 자동 다운로드용)

> Python이 없어도 걱정하지 마세요! 자동으로 설치됩니다.

## 🖨️ 지원하는 프린터

- ✅ **Windows 프린터**: 시스템에 설치된 모든 프린터
- ✅ **USB 프린터**: ESC/POS 호환 영수증 프린터  
- ✅ **네트워크 프린터**: IP 주소 기반 연결
- ✅ **파일 출력**: 테스트 및 미리보기용

## ⚙️ 기본 설정

프로그램 실행 후:
1. **프린터 설정**: USB 또는 네트워크 프린터 선택
2. **Supabase 연동**: URL, API Key, Project ID 입력
3. **연결 테스트**: 정상 작동 확인

## 🔧 문제 해결

### 자주 발생하는 문제들
- **실행 정책 오류**: `build.ps1` 우클릭 → 속성 → 차단 해제
- **관리자 권한 오류**: UAC 창에서 "예" 클릭 (자동 해결)
- **Python 설치 실패**: [python.org](https://python.org)에서 직접 설치
- **프로그램 실행 안됨**: Windows Defender 예외 처리
- **프린터 인식 안됨**: 드라이버 재설치 또는 USB 포트 변경

> 📞 **도움이 필요하세요?** [Issues](../../issues)에서 문제를 신고하거나 기존 해결책을 확인하세요.

---

## 👨‍💻 개발자용 정보

### 개발 환경 설정
```powershell
# 저장소 클론
git clone https://github.com/your-username/posprinter_supabase.git
cd posprinter_supabase

# 가상환경 및 의존성 설치
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 생성)
# SUPABASE_URL, SUPABASE_API_KEY, SUPABASE_PROJECT_ID 등 설정

# 개발용 실행
python main.py
```

### 배포용 빌드
```powershell
# 개발자용 배포 (버전 지정)
.\deployment_guide.ps1 -Version "1.0.0" -OutputPath ".\release"

# 또는 간단한 빌드
.\build.ps1
```

## 📁 프로젝트 구조

```
posprinter_supabase/
├── main.py                 # 🎯 메인 프로그램
├── build.ps1               # 🛠️ 비개발자용 빌드 스크립트
├── deployment_guide.ps1    # 🚀 개발자용 배포 스크립트
├── POSPrinter.spec         # 📦 PyInstaller 설정
├── requirements.txt        # 📋 Python 의존성
├── INSTALLATION_GUIDE.md   # 📖 설치 가이드
├── src/
│   ├── gui/                # 🖥️ 사용자 인터페이스
│   ├── printer/            # 🖨️ 프린터 제어
│   ├── database/           # 💾 데이터베이스 연동
│   ├── supabase_client.py  # ☁️ Supabase 클라이언트
│   ├── updater.py          # 🔄 자동 업데이트
│   └── error_logger.py     # 📝 오류 로깅
└── venv/                   # 🐍 Python 가상환경
```

## 🔄 업데이트

- **자동 업데이트**: 프로그램 실행 시 새 버전 자동 확인
- **수동 업데이트**: 새 버전 다운로드 후 `build.ps1` 재실행

## 📈 버전 정보

### 현재 버전: v1.0.0
- ✨ 초기 릴리즈
- 🔗 Supabase 완전 연동
- 🖨️ 다중 프린터 지원
- 🎨 직관적인 GUI
- 🔄 자동 업데이트 시스템
- 📊 실시간 주문 처리

## 🤝 기여하기

1. **버그 신고**: [Issues](../../issues)에서 문제 제보
2. **기능 제안**: 새로운 아이디어나 개선사항 제안
3. **코드 기여**: Pull Request로 코드 개선 참여

## 📞 지원

- **📋 Issues**: [GitHub Issues](../../issues)
- **📧 이메일**: 개발팀 직접 연락
- **📖 문서**: [설치 가이드](INSTALLATION_GUIDE.md)

---

## 🏆 특징

- 🚀 **원클릭 설치**: 복잡한 설정 없이 바로 사용
- ☁️ **클라우드 연동**: Supabase 실시간 데이터 동기화  
- 🖨️ **다양한 프린터**: USB, 네트워크, 시스템 프린터 모두 지원
- 🔄 **자동 업데이트**: 최신 기능을 자동으로 유지
- 💡 **사용자 친화적**: 직관적인 인터페이스
- 🛡️ **안정성**: 오류 처리 및 로깅 시스템

**⚠️ Windows 전용 프로그램입니다. 문제 발생 시 로그 파일을 확인하고 정기적으로 백업하세요.** 