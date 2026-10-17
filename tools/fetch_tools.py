# -*- coding: utf-8 -*-
"""빌드에 필요한 외부 자료를 공식 배포처에서 받아 work/에 풀고 SHA-256을 대조한다.
- 갈무리 v2.40.4 (quiple/galmuri, SIL OFL 1.1): Galmuri7.ttf, Galmuri9.ttf
- asar v1.91 (RPGHacker/asar): asar.exe"""
import hashlib, io, os, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, 'work')
ITEMS = [
    ('https://github.com/quiple/galmuri/releases/download/v2.40.4/Galmuri-v2.40.4.zip', 'galmuri', {
        'Galmuri7.ttf': 'c845c6bf6f7236ed370aed4a8f8d9b4f25e6a18f63515777fe4153d287c32917',
        'Galmuri9.ttf': 'e84e821b18be15b9e3a907ceb83cfba25fabf51c80b7edf0d2921cf8f8e1a11d'}),
    ('https://github.com/RPGHacker/asar/releases/download/v1.91/asar191.zip', 'asar', {
        'asar.exe': 'ecb04bce4a9a5a3b4dab4c9fafdc7875f30763fec15dec640b9cac11e11496e8'}),
]

for url, sub, want in ITEMS:
    dst = os.path.join(WORK, sub); os.makedirs(dst, exist_ok=True)
    if all(os.path.exists(os.path.join(dst, f)) for f in want):
        print('있음', sub)
    else:
        print('받는 중', url)
        z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(url).read()))
        for info in z.infolist():
            name = os.path.basename(info.filename)
            if name in want:
                open(os.path.join(dst, name), 'wb').write(z.read(info))
    for f, h in want.items():
        got = hashlib.sha256(open(os.path.join(dst, f), 'rb').read()).hexdigest()
        assert got == h, f'{f} 해시 불일치: {got}'
        print('확인', f)
