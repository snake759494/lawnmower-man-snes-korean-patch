# 빌드

Windows, Python 3.10 이상에서 확인했습니다.

```powershell
pip install -r requirements.txt
python tools/fetch_tools.py          # 갈무리 v2.40.4, asar v1.91을 work/에 받고 해시 대조
python tools/build.py 'Lawnmower Man, The (USA).sfc' 'work/Lawnmower Man, The (USA) (Korean).sfc'
xdelta3 -f -0 -S none -D -e -s 'Lawnmower Man, The (USA).sfc' 'work/Lawnmower Man, The (USA) (Korean).sfc' Lawnmower_Man_SNES_KR.xdelta
```

- `build.py`는 원본 ROM의 SHA-256을 먼저 검사합니다(헤더 없는 1,048,576바이트).
- 출력 마지막 줄의 SHA-256이 README의 `output`과 같으면 릴리즈와 동일한 ROM입니다.
- 화면당 한글 글자 수가 127을 넘거나, 줄이 32칸을 넘거나, 메시지가 16칸을 넘으면 빌드가 실패합니다.
- 타이틀 로고는 `data/title_logo_ko.png`(224×32, 색 번호 0~4)를 그대로 넣습니다.
