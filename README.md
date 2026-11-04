# SWP Shipyard 재구현 시작 패키지

명세와 참고 자료만으로 조선소 통합관리 시스템을 새로 구현한다. 이 폴더에는 기존 앱 코드가 없다.

## 1. 복사

```bash
cp -R rebuild-starter ~/work/shipyard-rebuild
cd ~/work/shipyard-rebuild
git init
```

## 2. 사전 준비

- Claude Code (로그인 완료)
- Node.js 18, 20 또는 22 이상 (19·21 제외), npm
- Python 3.10 이상, [uv](https://docs.astral.sh/uv/)
- Google Chrome (Playwright MCP 기본 브라우저)
- 첫 실행 시 npm·PyPI 패키지를 받을 네트워크
- Unity 6000.5.10f1 + Web Build Support + Unity Hub 로그인 (3D 뷰어 단계에만 필요)

Unity는 자동으로 설치되지 않는다. 없으면 나머지 단계를 진행한 뒤 해당 단계에서 멈추고 필요한 조치를 안내한다.

## 3. 실행

```bash
claude
```

폴더 신뢰와 Playwright MCP 사용을 승인한 뒤 입력한다.

```text
/rebuild
```

중단돼도 다시 `/rebuild`를 입력하면 `PROGRESS.md`의 다음 단계부터 이어간다. 긴 세션은 Claude Code의 기본 자동 압축을 사용한다. 세션을 새로 시작할지는 사용자가 정한다.

## 4. 실험 기록

`/rebuild` 전에 `PROGRESS.md` 맨 위에 적는다: 시작 시각, 모델(`/model`), `claude --version`, `node -v`, `uv --version`, Unity 버전. `@playwright/mcp` 버전은 `.mcp.json` 값이다.

끝나면 시각을 적고 프로젝트 폴더에서 사용량을 집계한다. 세션 로그를 응답 ID로 중복 제거해 합산하며 서브에이전트를 포함한다.

```bash
python3 - <<'PY'
import collections,glob,json,os,re
d=os.path.expanduser('~/.claude/projects/'+re.sub(r'[^0-9A-Za-z]','-',os.getcwd()))
u={}
for f in glob.glob(d+'/**/*.jsonl',recursive=True):
    for l in open(f,errors='ignore'):
        try: m=json.loads(l).get('message')
        except ValueError: continue
        if isinstance(m,dict) and m.get('usage') and m.get('id'): u[m['id']]=m
t=collections.Counter()
for m in u.values():
    t.update({k:v for k,v in m['usage'].items() if isinstance(v,int)})
print(len(u),dict(t),collections.Counter(m.get('model') for m in u.values()))
PY
```

입력·출력·캐시 생성·캐시 읽기를 나눠 기록한다.
# shipyard-TokenOptimization
