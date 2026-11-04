#!/bin/sh
# Web 빌드. 같은 프로젝트를 Editor로 열어 둔 상태에서는 실패한다.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNITY="${UNITY:-/Applications/Unity/Hub/Editor/6000.5.10f1/Unity.app/Contents/MacOS/Unity}"
"$UNITY" -batchmode -quit -buildTarget WebGL -projectPath "$ROOT/unity/ShipyardViewer" \
  -executeMethod ViewerBuild.Build -logFile "$ROOT/logs/unity-build.log"
