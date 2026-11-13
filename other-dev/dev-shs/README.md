# 안면 표정 검증 연구 (AI-Hub 랜드마크 샘플)

AI-Hub "안면 인식 랜드마크" *샘플*(피험자 10명 × 표정 7종 × 조명 3단계 = 이미지 210장)로 **평가 설계**를
다룬 작은 통제 연구입니다. 최고 성능을 주장하는 연구가 아닙니다.
방법, 결과, 한계: [`methodology_cvpr2027.md`](methodology_cvpr2027.md).
생성된 수치: [`results/cvpr2027/RESULTS.md`](../../results/cvpr2027/RESULTS.md).

## 데이터는 이 저장소에 없습니다

이미지, JSON 주석, OBJ 메시는 실제 사람의 얼굴이며 AI-Hub가 자체 약관에 따라 배포합니다. **커밋하지
마세요**(`.gitignore`에 등록되어 있습니다). 샘플은 AI-Hub에서 직접 내려받아 버전 관리 밖에 두세요.

> 이 데이터는 이전 커밋에서 이 저장소에 커밋된 적이 있습니다. 작업 트리에서 지워도 git 이력이나 기존
> 클론에서는 지워지지 않습니다. 문서 끝의 안내를 참고하세요.

### 필요한 폴더 구조

`--data-root`(또는 환경 변수 `FACE_DATA_ROOT`)로 `01.원천데이터`와 `02.라벨링데이터`가 들어 있는 폴더를
지정합니다. 둘 다 지정하지 않으면 스크립트는 저장소 루트 기준 `dev-YuIK/안면_인식_랜드마크_Sample`을
찾습니다.

```
<data-root>/
├── 01.원천데이터/
│   ├── image/
│   │   └── F1350/ … F1359/            피험자마다 폴더 하나
│   │       └── F1350_01_1_H.png       <피험자>_<표정 코드>_<촬영 번호>_<조명>.png  (1440×1080 RGB)
│   └── 3D data/
│       └── F1350/ … F1359/
│           └── F1350_01_1_H.obj       이미지와 같은 이름 (학습에는 필요 없음)
└── 02.라벨링데이터/
    └── F1350/ … F1359/
        └── json/
            └── F1350_01_1_H.json      이미지와 같은 이름
```

- 표정 코드: `01` Joy, `02` Neutral, `03` Surprise, `04` Disgust, `05` Sadness, `06` Anger, `07` Fear.
- 조명 코드: `H` highlight, `M` middlelight, `L` lowlight.
- 사용하는 JSON 필드: `expression`(라벨), `light`(분할과 보고에만 사용), `3Dlandmark`(`v x y z` 1,220줄),
  `face`(`f i j k` 2,304줄, 1부터 시작하는 인덱스). `age`, `gender`, `id`, `proficiency`도 있지만 모델
  입력으로 쓰지 않습니다.
- 각 OBJ에는 JSON과 같은 정점 1,220개와 면 2,304개가 있고, 그 뒤에 `z = 0`인 `v` 1,220줄의 두 번째 블록이
  이어집니다. 이 블록은 모든 파일에서 동일합니다(`mesh_provenance.py` 참고).

## 실행

저장소 루트에서, 사용하는 CUDA 또는 CPU 환경에 맞는 PyTorch/torchvision 빌드로 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r other-dev/dev-shs/requirements.txt

# 1. 메시 출처 점검 (몇 초, CPU)
.\.venv\Scripts\python.exe other-dev/dev-shs/mesh_provenance.py --data-root <data-root>

# 2. 전체 실험 (GPU 한 장으로 몇 시간, 이어서 실행 가능: 끝난 실행은 건너뜀)
.\.venv\Scripts\python.exe other-dev/dev-shs/run_validation.py --data-root <data-root> --stage all

# 3. 통계, 표, 그림
.\.venv\Scripts\python.exe other-dev/dev-shs/analyze_results.py
```

`run_validation.py --smoke --output-dir <임시 폴더>`는 파이프라인 점검용으로 모든 프로토콜을 fold 두 개에
대해 1 epoch씩 돌립니다. `--stage`에는 `manifest`, `inner`, `loso`, `splits`, `lightout`, `lightmatch`,
`all` 중 하나를 줄 수 있습니다.

실행이 중간에 끊겨 로그 끝에 깨진 레코드가 남아도, 다음 실행은 그 줄을 경고와 함께 건너뛰고 해당 작업만 다시
돌립니다.

## 생성되는 파일 (`results/cvpr2027/`)

| 파일 | 내용 |
|---|---|
| `split_manifest.csv` | 모든 프로토콜의 모든 학습/테스트 분할. 학습 **전에** 기록함 (SHA-256은 `environment.json`에 있음) |
| `environment.json`, `data_summary.json` | 패키지 버전, 장치, git 커밋, 하이퍼파라미터, 시드, 데이터셋 개수 (상대 경로만 기록) |
| `flip_permutation.json` | LOSO 학습 템플릿별 좌우 정점 순열 진단 |
| `epoch_selection.csv`, `epoch_selection_inner_runs.csv` | 후보 epoch 수별 내부 CV 정확도와 선택된 값 |
| `logs/runs.jsonl` | 학습 실행마다 레코드 하나: 시드, epoch, 옵티마이저 스텝, epoch별 학습 손실, 테스트 확률, 소요 시간 |
| `logs/run_stdout.log` | 실험의 콘솔 로그 |
| `predictions_{loso,random,triplet,lightout,lightmatch}.csv` | 이미지별 예측과 클래스 확률 |
| `mesh_provenance.json` | JSON과 OBJ의 비교, 조명에 따른 메시 변화 |
| `analysis/` | 요약 표, 대응 대비, 혼동행렬, 보정 구간, 그림 |
| `RESULTS.md` | 보고하는 모든 표. 위 파일들에서 생성함 |

`RESULTS.md`의 문장과 모델 이름은 한국어이고, 그림의 글자와 CSV의 열 이름은 영어입니다.

모델 체크포인트는 저장하지 않습니다. 검증 데이터나 테스트 데이터로 고르는 것이 없으므로, 마지막 epoch
가중치를 한 번 평가한 뒤 버립니다. `results/legacy_5fold_v1/`에는 대체된 첫 실험(5-fold, 검증으로 고른
체크포인트, 경과 시간 기반 스케줄)이 참고용으로만 남아 있습니다.

## 데이터 관리 안내

파일을 추적에서 제외해도 이력에서 삭제되지는 않습니다. 얼굴 이미지, JSON/OBJ 메시, 모델 체크포인트는 이
저장소의 이전 커밋과 모든 클론 및 포크에서 여전히 접근할 수 있습니다. 이를 없애려면 이력을 다시 쓰고(예:
`git filter-repo`) 강제 푸시해야 하며, 모든 협업자가 함께 조율해야 합니다. 또 샘플의 재배포가 어디까지
허용되는지 AI-Hub/NIA에 확인해야 합니다. 이 결정은 저장소 소유자와 지도교수의 몫이며, 여기서는 수행하지
않았습니다.
