# 응급 환자 골든타임 사수를 위한 지역 병원 병상 & 이동 동선 통합 제어

국립한국교통대학교 컴퓨터소프트웨어학과 26년도 캡스톤 디자인 G팀
담당 파트: 유익(AI 및 데이터 전처리)

## 1. 프로젝트 개요

본 프로젝트는 구급차 내 환자의 생체 신호와 현장 외상 임상 이미지를 수집하여
환자 중증도를 파악하고, 병원의 실시간 가용 자원과 연동하는 시스템이다.

1. 딥러닝 기반 다중 중증도 분류: 외상 이미지와 안면·안구 데이터를 분석한다.
2. 동적 병원 라우팅: 중증도와 지역 응급의료기관 자원을 결합해 이송 병원을
   매핑하고 이동 동선을 제어한다.

응급 의료 체계의 핵심인 골든타임 확보와 이송 지연 문제 해결을 목표로 한다.

## 2. 주요 특징

- **다중 모달리티 데이터 처리**: 외상·질환 이미지, 오디오, 안면·신체 관절
  랜드마크 등 서로 다른 형태의 데이터를 전처리하고 통합한다.
- **경량 구조화 데이터 파이프라인**: MediaPipe/Yolo-pose 수치 데이터에서
  안면 비대칭도와 관절 각도를 계산하고 응급도를 분류한다.
- **딥러닝 이미지 파이프라인**: PyTorch와 EfficientNet을 이용해 현재 외상
  이미지(`abrasions`, `bruises`, `cut`, `stab`)를 분류하며, 향후 화상 단계,
  피부질환, 약제 이미지로 확장한다.
- 현장 신뢰성을 위한 해석 가능한 AI(XAI), 재현성, 온디바이스 최적화를 고려한다.

## 3. 현재 아키텍처 및 워크플로우

현재 wound 데이터는 Roboflow COCO export의 바운딩 박스를 먼저 crop한 뒤
crop 이미지 분류기로 학습한다. 학습·검증·최종 테스트의 역할을 분리하여
test split은 `--evaluate-test`를 명시한 경우에만 마지막에 한 번 평가한다.

```text
COCO train/valid/test
        │
        ▼
datasets/wound_dataset.py
  └─ 안전한 bbox 검증·crop → dataset/<split>/<class>/*.jpg
        │
        ├─ utils/transforms.py  (train augmentation / val-test deterministic transform)
        ├─ models/efficientnet.py (EfficientNet-B0 + MLP head)
        └─ scripts/train_wound.py
             └─ loss / optimizer / scheduler / checkpoint / metrics
```

## 4. 디렉터리 구조

```text
dev-YuIK/
├── emergency_cdss/
│   ├── __init__.py
│   ├── datasets/
│   │   ├── __init__.py
│   │   ├── wound_dataset.py        # 현재 구현: COCO crop + wound loader
│   │   ├── burn_dataset.py         # 구현: 폴더형 화상 단계 loader
│   │   └── landmark_dataset.py     # 구현: 고정 길이 수치/랜드마크 loader
│   ├── models/
│   │   ├── __init__.py
│   │   ├── efficientnet.py         # WoundEfficientNet
│   │   └── triage_mlp.py           # 수치형 triage branch
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── metrics.py              # accuracy, macro-F1, balanced accuracy
│   │   └── transforms.py           # ImageNet 전처리/증강
│   ├── scripts/
│   │   ├── __init__.py
│   │   ├── train_wound.py          # 현재 학습 실행 진입점
│   │   ├── evaluate_wound.py        # test 수치·이미지 추론 진입점
│   │   └── train_triage.py         # 구조화/멀티모달 학습 scaffold
│   └── requirements.txt
└── dataset/                        # 생성 산출물·checkpoint·history
```

`dataset/`은 원본 `train/valid/test`의 하위 디렉터리가 아니어야 한다.
스크립트는 경로 탈출이 가능한 COCO 파일명과 잘못된 bbox를 거부하고, 기존
산출물이 있을 때는 실수로 삭제하지 않도록 `--overwrite`를 요구한다.

## 5. 설치 및 준비

`dev-YuIK`에서 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r emergency_cdss\requirements.txt
```

GPU를 사용하는 경우 PyTorch 공식 설치 안내에 따라 CUDA에 맞는 `torch`와
`torchvision`을 먼저 설치한 뒤 나머지 의존성을 설치한다. 오프라인에서
구조 검증만 할 때는 실제 학습을 실행하지 말고 Python 문법 검사를 사용할 수
있다.

## 6. 사용 방법

권장 실행 방식:

```powershell
cd dev-YuIK
python -m emergency_cdss.scripts.train_wound --epochs 25 --batch-size 32
```

주요 옵션 예시는 다음과 같다.

```powershell
# 검증 macro-F1을 기준으로 checkpoint 선택
python -m emergency_cdss.scripts.train_wound --selection-metric macro_f1

# backbone을 고정한 뒤 fine-tuning 시작
python -m emergency_cdss.scripts.train_wound --freeze-backbone-epochs 3

# 최종 학습 후 test split을 한 번 평가
python -m emergency_cdss.scripts.train_wound --evaluate-test

# checkpoint의 test 수치와 지정 이미지 예측 결과 출력
python -m emergency_cdss.scripts.evaluate_wound \
  --image dataset/test/abrasions/crop_000001_img1_ann1.jpg \
  --output-json evaluation_results.json

# 원본 사진에서 bbox를 지정해 crop 후 예측 이미지 저장
python -m emergency_cdss.scripts.evaluate_wound \
  --image path/to/photo.jpg --bbox 20 30 240 180 \
  --save-annotated-dir predictions

# 인터넷/사전학습 가중치 없이 smoke test 또는 오프라인 실행
python -m emergency_cdss.scripts.train_wound --no-pretrained --epochs 1 --num-workers 0
```

학습 시 `train`, `valid`, `test` 폴더에 `_annotations.coco.json`이 있어야 하며,
현재 wound 클래스 순서는 `abrasions`, `bruises`, `cut`, `stab`으로 checkpoint에
함께 기록된다. 기본 산출물은 `dataset/best_efficientnet_b0_wound.pt`와
`dataset/training_history.json`이다.

## 7. 모듈별 책임과 확장 지점

| 모듈 | 책임 | 향후 확장 방향 |
|---|---|---|
| `datasets/wound_dataset.py` | COCO annotation 검증, 안전한 crop, wound folder loader | wound segmentation·다중 bbox 정책 분리 |
| `datasets/burn_dataset.py` | `root/class/*.jpg` 화상 이미지 loader | 1~3도 라벨 정책, 화상 면적/체표면적 메타데이터 추가 |
| `datasets/landmark_dataset.py` | `[N, F]` 수치 feature와 label tensor화 | 얼굴·자세·임상 수치·stroke 경과 시계열 전용 collate 추가 |
| `models/efficientnet.py` | 이미지 분류 backbone과 classifier head | burn/피부질환/약제별 backbone 또는 multi-head 구성 |
| `models/triage_mlp.py` | 랜드마크·임상 수치용 구조화 데이터 branch | image embedding과 late-fusion하는 multimodal head 구성 |
| `utils/transforms.py` | 이미지 크기 조정, train augmentation, ImageNet 정규화 | modality별 augmentation 정책 분리 |
| `utils/metrics.py` | accuracy, macro-F1, balanced accuracy, confusion matrix | AUROC, calibration, sensitivity/specificity 추가 |
| `scripts/train_wound.py` | wound 학습 orchestration 및 checkpoint 저장 | `evaluate.py`, config 기반 실행 추가 |
| `scripts/evaluate_wound.py` | test 수치 출력, 혼동행렬, 지정 이미지 추론, JSON/annotated 결과 저장 | batch inference·threshold/calibration 추가 |
| `scripts/train_triage.py` | 향후 구조화/멀티모달 학습 진입점 scaffold | manifest·label·patient split 확정 후 구현 |

### 향후 데이터 추가 원칙

1. 원본 데이터와 전처리 산출물을 분리하고, 각 샘플에 `patient_id` 또는
   `case_id`를 보존한다. 같은 환자의 이미지가 train과 valid/test에 동시에
   들어가면 데이터 누수로 성능이 과대평가될 수 있다.
2. 이미지·임상 수치·stroke 경과관찰처럼 시간축이 있는 데이터는 먼저 공통
   sample manifest를 정의한 뒤 dataset loader가 그 manifest를 읽도록 한다.
3. 합성 데이터는 `synthetic: true`, 생성 모델/버전, 원본 또는 seed 메타데이터를
   기록하여 실제 데이터와 성능을 분리해 평가한다.
4. 약제 이미지와 피부질환 이미지는 현재 wound 클래스와 섞지 말고 별도 label
   space를 사용한다. 통합 triage가 필요할 때만 명시적인 fusion/head에서 결합한다.
5. 3D 인체·자세 데이터는 프레임 단위 수치 feature와 sequence 단위를 구분한다.
   현재 `LandmarkDataset`은 고정 길이 `[N, F]` 입력용이며, 시계열 모델은
   별도의 padding/mask 정책을 추가해야 한다.

## 8. 라이선스

본 프로젝트는 MIT 라이선스를 따른다.

## 9. 참고 기술

PyTorch, torchvision, timm, Pillow, NumPy, EfficientNet, COCO annotations,
MediaPipe/Yolo-pose 계열 랜드마크 처리 기술을 사용한다.
