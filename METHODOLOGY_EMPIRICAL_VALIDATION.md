# Facial Landmark-based Multi-Modal Classification 정리

> 목표: RGB 얼굴 crop과 3D facial landmark를 결합해 얼굴 상태/표정 클래스를 분류하고, EfficientNet-B0 image-only baseline과 landmark-fused 모델을 동일한 identity-disjoint protocol에서 비교한다.
>
> 데이터 근거: 사용자가 제공한 공개 Google Drive 폴더의 image/, 3D data/, 02.라벨링데이터/ 구조와 확인된 JSON 스키마를 반영했다.
>
> 보충 설명: 손실함수, AUROC/PR 계산, identity split, edge latency, 통계 보고 원칙은 데이터 폴더에 명시되지 않은 일반적인 딥러닝·실험 설계 지식으로 보완했다.

## 1. 핵심 개념 요약

| 핵심 개념 | 한 문장 요약 | 개념 간 관계 |
|---|---|---|
| **RGB image branch** | 얼굴 crop의 색상·텍스처·조명·윤곽을 EfficientNet-B0로 인코딩한다. | appearance 정보를 담당한다. |
| **Landmark branch** | JSON의 3Dlandmark OBJ 정점 문자열을 [x,y,z] 좌표 텐서로 파싱하고 MLP로 투영한다. | geometry와 deformation 정보를 담당한다. |
| **Feature-level fusion** | 두 branch의 임베딩을 concatenation한 뒤 projection head를 거쳐 분류한다. | appearance와 geometry의 상보성을 사용한다. |
| **Identity-disjoint split** | 같은 사람의 샘플이 train/valid/test에 동시에 들어가지 않도록 subject 단위로 분할한다. | 일반화 성능의 과대평가를 막는다. |
| **Macro F1 / Balanced Accuracy** | class별 F1 또는 recall을 동일 가중치로 평균한다. | class imbalance에 강한 primary metric이다. |
| **AUROC / PR curve** | 확률 threshold 변화에 따른 순위·검출 품질을 평가한다. | 고정 threshold 의존성을 줄인다. |
| **Spatial asymmetry / geometric shift** | landmark 좌우 반사 오차와 기준 형상 대비 이동량을 수치화한다. | 구조적 근거와 failure mode를 설명한다. |
| **6×6 qualitative grid** | test 샘플 36개에 GT·prediction·confidence를 표시한다. | 수치 지표 밖의 오류를 확인한다. |

핵심 흐름은 **RGB/landmark 입력 → modality별 encoder → feature fusion → MLP classifier → 수치·시각 평가**이다.

## 2. 주요 용어 정리

| 용어 | 정의 | 시험/리뷰 포인트 | 예시 |
|---|---|---|---|
| **EfficientNet-B0** | 정확도와 연산량을 균형화한 경량 CNN backbone | edge deployment를 위해 compactness를 함께 보고한다. | ImageNet-pretrained B0 |
| **MLP head** | 선형층·활성화·dropout 기반 task-specific classifier | backbone feature를 직접 softmax에 넣지 않고 투영한다. | Linear → GELU → Dropout → Linear |
| **3D landmark** | 얼굴 mesh vertex 좌표 집합 | 원본 JSON은 v x y z 문자열이다. | 1,220 vertex × 3좌표 |
| **Face topology** | OBJ f 면 정보 | primary MLP 입력과 구분하고 후속 GNN에 보존한다. | 2,304 face 문자열 |
| **Feature-level fusion** | 중간 feature를 결합하는 방식 | logits 평균이 아니라 representation을 joint learning한다. | [h_img; h_lm] |
| **Identity leakage** | 동일 인물 샘플이 서로 다른 split에 들어가는 현상 | random image split의 가장 큰 위험이다. | F1350이 train/test 양쪽에 존재 |
| **Macro F1** | class별 F1의 산술평균 | rare class를 무시하지 않는다. | 7개 expression F1 평균 |
| **Balanced Accuracy** | class별 recall의 평균 | 1/K Σ recall_k |
| **AUROC** | one-vs-rest ROC 곡선 아래 면적 | class support가 없으면 정의되지 않는다. | macro AUROC |
| **PR curve** | threshold별 precision-recall 배열 | rare positive class에 유용하다. | class별 curve |
| **Edge latency** | 고정 device에서 한 sample을 추론하는 시간 | p50/p95와 preprocessing 포함 여부를 구분한다. | ms/sample |

## 3. 세부 내용 정리

### 3.1 문제 정의와 데이터 스키마

#### 개념

샘플을 다음과 같이 정의한다.

\[
\mathcal{D}=\{(I_i,L_i,y_i,s_i,v_i)\}_{i=1}^{N}
\]

- I_i: RGB 얼굴 crop 또는 얼굴 중심 PNG
- L_i: 3D facial landmark 좌표 [P,3]
- y_i: JSON의 expression target
- s_i: subject identity
- v_i: 파일 suffix H/L/M

#### 핵심 내용

Drive에서 확인한 대응 구조는 다음과 같다.

~~~text
image/F1350/F1350_01_1_H.png
02.라벨링데이터/F1350/json/F1350_01_1_H.json
~~~

확인된 JSON 필드는 filename, gender, id, proficiency, age, expression, light, 3Dlandmark, face다. 3Dlandmark는 v x y z 문자열 1,220개이고, face는 f i j k 문자열 2,304개다. F1350 샘플에서 expression의 7개 class(Anger, Disgust, Fear, Joy, Neutral, Sadness, Surprise)를 확인했다. 전체 class count는 dataset_summary.json으로 다시 검증한다.

#### 왜 중요한가?

이미지와 JSON은 동일한 stem으로 매칭되어야 한다. gender, age, light 등을 입력으로 무심코 넣으면 expression보다 metadata shortcut을 학습할 수 있으므로, 기본 모델 입력과 분석용 metadata를 분리한다.

#### 예시

~~~json
{"filename":"F1350","expression":"Joy","3Dlandmark":["v -0.02 -2.92 5.43"],"face":["f 1202 45 46"]}
~~~

#### 시험/리뷰 포인트

- face는 target label이 아니라 mesh connectivity다.
- 별도 bbox annotation이 확인되지 않은 경우 제공된 face-centered PNG를 crop 입력으로 사용한다.
- explicit bbox가 확보되면 manifest의 image path만 crop 결과로 교체한다.
- dense mesh vertices와 semantic landmarks를 논문에서 구분해 표현한다.

### 3.2 전처리와 landmark 정규화

#### 개념

이미지와 좌표의 단위가 다르므로 modality별 정규화를 적용한다.

#### 핵심 내용

이미지는 RGB 변환, source 픽셀에 존재하는 고정 90° counter-clockwise 회전 보정, 224×224 resize, ImageNet mean/std normalization을 사용한다. train에서는 vision-only에 flip/rotation/color jitter를 허용하고, joint 모델에서는 좌표와 이미지의 정합성을 위해 color jitter 위주로 사용한다. 이 90° 보정은 EXIF metadata가 아니라 실제 PNG 픽셀 방향을 확인해 적용한 데이터 품질 보정이다. **보충 설명**

랜드마크는 다음처럼 canonicalize한다.

\[
\tilde{L}_{i,p}=\frac{L_{i,p}-\mu_i}{\max_q\|L_{i,q}-\mu_i\|_2+\epsilon},\quad
\mu_i=\frac{1}{P}\sum_{p=1}^{P}L_{i,p}
\]

#### 왜 중요한가?

centroid subtraction과 scale normalization은 촬영 위치·얼굴 크기의 nuisance를 줄이고 상대적인 표정 deformation을 보존한다.

#### 예시

~~~python
vertices = parse_obj_vertices(payload["3Dlandmark"])  # [1220, 3]
landmarks = normalize_landmarks(vertices).reshape(-1)   # [3660]
~~~

#### 시험/리뷰 포인트

이미지에만 공간 변환을 적용하면 RGB와 landmark가 서로 다른 얼굴을 나타낸다. paired affine transform을 구현하기 전에는 joint model에서 spatial augmentation을 제한한다.

### 3.3 Identity-disjoint split

#### 개념

sample이 아니라 identity를 먼저 섞어 train/valid/test에 배정한다.

#### 핵심 내용

기본 구현은 seed 42, 60/20/20 subject split이다. 한 subject의 모든 view와 condition은 같은 partition에 함께 들어간다.

#### 왜 중요한가?

같은 사람의 다른 조명·표정 이미지를 train과 test에 동시에 넣으면 모델이 expression이 아니라 얼굴 identity를 기억해도 높은 점수를 얻는다. 이는 신규 환자/identity 성능이 아니다.

#### 예시

~~~text
train: F1350–F1355
valid: F1356–F1357
test : F1358–F1359
~~~

#### 시험/리뷰 포인트

split 이후 train∩valid, train∩test, valid∩test가 모두 공집합인지 assertion한다. subject 수가 적으므로 최종 제출에서는 repeated group split 또는 leave-one-subject-out confidence interval을 추가하는 것이 바람직하다. **보충 설명**

### 3.4 EfficientNet-B0 image branch

#### 개념

EfficientNet-B0는 제한된 edge resource에서 정확도·연산량·parameter 수를 균형화하는 image encoder다.

#### 핵심 내용

\[
h_i=f_{B0}(I_i)\in\mathbb{R}^{d_I}
\]

timm.create_model("efficientnet_b0", num_classes=0)로 pooled image feature를 얻고 MLP head에서 class logits를 계산한다.

~~~text
RGB 224×224×3 → EfficientNet-B0 → image feature
                 → Linear → GELU → Dropout → Linear(K)
~~~

#### 왜 중요한가?

대형 backbone은 성능을 높일 수 있지만 memory와 latency를 증가시킨다. parameter count, input size, CPU/GPU latency를 함께 report해야 compact model 주장이 성립한다.

#### 시험/리뷰 포인트

pretrained policy, backbone freeze 여부, class order, parameter count를 checkpoint metadata에 저장한다. baseline과 joint는 backbone과 optimizer를 동일하게 유지한다.

### 3.5 Landmark branch와 fusion

#### 개념

정규화된 coordinate vector를 MLP로 encoding하고 image feature와 결합한다.

\[
h_l=MLP(\operatorname{vec}(\tilde{L})),\qquad
h_f=GELU(LN(W_f[h_i;h_l]+b_f))
\]

#### 핵심 내용

~~~text
3660-D coordinates → LayerNorm → Linear(3660→128)
                   → GELU → Dropout → Linear(128→128)

[image feature ; landmark feature]
                   → fusion projection(256-D)
                   → MLP classifier
~~~

vision-only는 h_i만 classifier로 전달하고, joint는 [h_i;h_l]를 projection한다. primary model은 dense coordinate MLP이며 face adjacency 기반 GNN은 후속 ablation이다.

#### 왜 중요한가?

RGB는 appearance·texture에 강하지만 조명에 취약할 수 있고, landmark는 상대적 얼굴 geometry를 직접 표현한다. feature-level fusion은 두 정보원을 decision 이전에 상호작용시킨다.

#### 시험/리뷰 포인트

landmark 순서가 모든 샘플에서 동일하다는 전제가 필요하다. semantic index map이 없으므로 nearest reflected point를 쓰는 asymmetry metric의 가정을 명시한다.

### 3.6 학습과 평가

#### 개념

cross entropy로 target class의 log-probability를 최대화한다.

\[
\mathcal{L}=-\frac{1}{B}\sum_{i=1}^{B}\log p_{i,y_i}
\]

#### 핵심 내용

| 항목 | 기본값 | 목적 |
|---|---:|---|
| Optimizer | AdamW | decoupled weight decay |
| Learning rate | 3e-4 | 보수적 fine-tuning |
| Weight decay | 1e-4 | 과적합 완화 |
| Scheduler | cosine | 안정적 감쇠 |
| Batch / input | 16 / 224 | 8GB GPU 기본값 |
| Epoch | 25 이상 | fixed epoch 실행 |
| Seed | 42 | baseline/joint 동일 비교 |

validation Macro F1이 최고인 checkpoint를 선택하고, test는 선택된 checkpoint로 마지막에 한 번만 추론한다. --schedule-hours 8은 8시간 schedule과 runtime 기록을 활성화한다. 실제 완료 여부는 runtime_seconds와 log로 확인하며 숫자를 임의로 채우지 않는다.

#### 왜 중요한가?

작은 identity 수에서는 validation 분산이 크다. test를 checkpoint selection에 쓰거나 반복 확인하면 test leakage가 생긴다.

#### 시험/리뷰 포인트

“8시간 budget을 지정했다”와 “실제로 8시간 실행을 완료했다”는 다르다. completed epochs와 wall-clock을 함께 보고한다.

## 4. 비교 정리

### 4.1 Vision-only vs. joint

| 구분 | Vision-only baseline | Joint landmark-fused |
|---|---|---|
| 입력 | RGB crop | RGB crop + 3D coordinates |
| Backbone | EfficientNet-B0 | 동일한 EfficientNet-B0 |
| Structured branch | 없음 | LayerNorm + 2-layer MLP |
| Fusion | 없음 | concat + projection |
| Spatial augmentation | 가능 | paired transform 전에는 제한 |
| 장점 | 단순·빠름 | appearance와 geometry 상보성 |
| 핵심 비교 | 기준점 | joint − vision 개선량 |

### 4.2 지표 비교

| 구분 | Accuracy | Macro F1 | Balanced Accuracy |
|---|---|---|---|
| 계산 | 전체 정답 비율 | class별 F1 평균 | class별 recall 평균 |
| 불균형 대응 | 약함 | 강함 | 강함 |
| precision 반영 | 아니오 | 예 | 아니오 |
| 역할 | 보조 | primary | primary |

| 구분 | AUROC | PR curve |
|---|---|---|
| 축 | FPR–TPR | Recall–Precision |
| 장점 | ranking 품질 | rare positive에 직관적 |
| 주의 | support 없는 class는 NaN | prevalence 영향을 받음 |

## 5. 절차 / 과정 정리

1. **Drive discovery**
   - 수행 내용: public folder의 stable ID를 이용해 label/image sample을 찾는다.
   - 목적: 브라우저 상태와 무관한 재현 가능한 데이터 준비.
   - 주의할 점: 이름이 아니라 file ID와 stem을 매칭한다.

2. **PNG–JSON pairing**
   - 수행 내용: 같은 stem의 PNG와 JSON을 하나의 manifest record로 결합한다.
   - 목적: 잘못된 supervision 방지.
   - 주의할 점: H/L/M suffix와 subject ID가 일치해야 한다.

3. **OBJ parsing and normalization**
   - 수행 내용: v x y z만 파싱하고 centroid/scale normalize한다.
   - 목적: geometry branch를 안정화한다.
   - 주의할 점: face 문자열은 coordinate로 파싱하지 않는다.

4. **Identity split**
   - 수행 내용: subject set을 seed 기반으로 train/valid/test에 배정한다.
   - 목적: patient/identity leakage 차단.
   - 주의할 점: split별 subject list를 결과에 저장한다.

5. **Fixed-epoch training**
   - 수행 내용: vision-only와 joint를 같은 config로 학습한다.
   - 목적: modality 차이의 효과를 분리한다.
   - 주의할 점: test로 checkpoint를 고르지 않는다.

6. **Final inference and export**
   - 수행 내용: best checkpoint로 test를 한 번 추론하고 metrics, predictions, PR/ROC points, geometry metrics, 6×6 grid를 저장한다.
   - 목적: 표·그림·failure analysis 재생성.
   - 주의할 점: 결과 숫자를 수기로 복사하지 않는다.

### 재현 명령

~~~powershell
cd dev-YuIK
py -m emergency_cdss.scripts.prepare_drive_landmark_data --output-dir dataset/drive_landmark --views H L M
py -m emergency_cdss.scripts.run_empirical_validation --manifest dataset/drive_landmark/manifest.json --output-dir dataset/face_experiments --epochs 25 --schedule-hours 8 --batch-size 16 --device cuda
~~~

GPU smoke test:

~~~powershell
py -m emergency_cdss.scripts.prepare_drive_landmark_data --output-dir dataset/drive_landmark_smoke --views H --limit-subjects 3
py -m emergency_cdss.scripts.train_face_multimodal --manifest dataset/drive_landmark_smoke/manifest.json --mode joint --epochs 1 --no-pretrained --device cuda
~~~

### 실행 결과 snapshot

실제 실행 artifact는 `dev-YuIK/dataset/face_experiments/`에 저장되었다. 설정은 10 identities, 210 records, H/L/M, 7 classes, seed 42, 동일 identity split, 25 fixed epochs, no-pretrained EfficientNet-B0, CUDA RTX 4070이었다. 총 8시간 protocol 안에서 각 모델에 4시간 allocation을 기록했지만, 데이터가 작아 두 모델 모두 약 4분 내에 fixed epochs와 test inference를 완료했다.

| 모델 | Params | Test Macro F1 | Balanced Accuracy | Macro AUROC | p50 ms/sample | p95 ms/sample |
|---|---:|---:|---:|---:|---:|---:|
| Vision-only | 4,337,283 | 0.1205 | 0.1667 | 0.4795 | 0.7693 | 0.8651 |
| Joint | 4,928,795 | 0.2021 | 0.2381 | 0.6997 | 0.8167 | 1.1859 |
| Joint − Vision | +591,512 | +0.0815 | +0.0714 | +0.2202 | +0.0474 | +0.3208 |

이 표는 pipeline 검증용 결과이며, 10명 identity의 단일 split과 no-pretrained 설정만으로 CVPR 일반화 주장을 확정하지 않는다. 최종 논문에서는 pretrained backbone, repeated identity split, confidence interval, class-wise PR/Calibration과 외부 test set을 추가한다. **보충 설명**

## 6. 그림/도식 설명

~~~mermaid
flowchart LR
    A[Drive image PNG] --> B[RGB resize / normalize]
    C[Drive JSON] --> D[Parse 3Dlandmark OBJ vertices]
    D --> E[Center + scale normalize]
    B --> F[EfficientNet-B0]
    E --> G[Landmark MLP]
    F --> H[Feature concatenation]
    G --> H
    H --> I[Fusion projection + MLP head]
    I --> J[Class probabilities]
    J --> K[Macro F1 / Balanced Acc / AUROC / PR]
    J --> L[6x6 qualitative grid]
~~~

그림을 해석할 때는 동일 sample stem이 image와 JSON을 연결하고, identity split이 encoder보다 먼저 적용된다는 점을 강조한다. Fusion은 logits를 평균하는 것이 아니라 feature 공간에서 일어난다.

### 6.1 6×6 grid 해석

각 cell에는 얼굴 crop, GT, predicted label, confidence, subject/view가 들어간다. 초록 테두리는 correct, 빨간 테두리는 incorrect다.

| 현상 | 해석 후보 | 추가 점검 |
|---|---|---|
| 특정 조명에서만 오류 | RGB illumination shortcut | H/L/M별 metric |
| 특정 identity에서만 오류 | identity distribution shift | leave-one-subject-out |
| high-confidence 오답 | calibration failure | reliability diagram |
| joint가 개선되지 않음 | branch mismatch 또는 noisy geometry | landmark ablation |

## 7. 시험 빈출 포인트

### 반드시 암기

- **공정한 baseline 비교**는 동일 split·seed·optimizer·epoch·pretrained policy에서 입력 modality만 바꾸는 것이다.
- **Macro F1**은 각 class F1을 동일 가중치로 평균한다.
- **Balanced Accuracy**는 class별 recall 평균이다.
- **Identity-disjoint split**은 같은 사람의 샘플이 train/valid/test에 동시에 들어가는 것을 막는다.
- JSON의 3Dlandmark는 문자열이므로 vertex parser가 필요하다.
- 이미지에만 spatial augmentation을 적용하면 joint branch의 입력 정합성이 깨진다.
- Test set은 checkpoint 선택에 사용하지 않는다.
- AUROC는 class별 one-vs-rest로 계산하고 macro 평균을 기록한다.
- PR curve는 threshold별 precision/recall 배열을 보존해야 재현 가능하다.
- parameter count와 latency는 compact edge model 주장을 뒷받침한다.

### 서술형 대비

- **왜 landmark fusion이 필요한가?** RGB는 appearance와 texture에 강하지만 조명·배경에 영향을 받으며, landmark는 상대적인 얼굴 구조와 deformation을 직접 표현한다. 따라서 feature-level fusion은 서로 다른 nuisance와 signal을 결합한다.
- **왜 random image split을 사용하지 않는가?** 동일 identity의 이미지가 train과 test에 함께 들어가면 개인별 얼굴 구조가 누수되어 신규 identity 성능이 과대평가된다.
- **왜 joint model의 spatial augmentation을 제한하는가?** 이미지가 회전·반전되는데 landmark 좌표가 같은 변환을 받지 않으면 두 modality가 서로 다른 geometry를 표현하기 때문이다.
- **왜 accuracy 하나만 보고하지 않는가?** imbalance에서는 다수 class 성능만으로 높아 보일 수 있으므로 Macro F1, Balanced Accuracy, AUROC와 class-level PR을 함께 보고한다.

### 헷갈리기 쉬운 부분

- 3Dlandmark는 float 배열이 아니라 **OBJ 문자열 목록**이다.
- face는 class label이 아니라 mesh face connectivity 정보다.
- AUROC와 average precision은 같은 값이 아니다.
- validation은 model selection용이고 test는 final report용이다.
- 8시간 budget을 지정했다고 실제 8시간 실행이 자동으로 보장되는 것은 아니다.

### 교수님/리뷰어가 문제 내기 좋은 부분

- identity leakage를 막는 split 코드와 split assertion
- vision-only와 joint의 parameter count 차이
- semantic left/right pairing이 없을 때 nearest reflected point 가정
- rare class에서 Macro F1·Balanced Accuracy가 accuracy와 다르게 움직이는 이유
- 6×6 grid에서 high-confidence failure의 원인을 분석하는 문제

## 8. 예상 문제

### 객관식

1. identity-disjoint split의 주된 목적은 무엇인가?
   - ① 학습 속도를 높인다.
   - ② 같은 identity의 유사 샘플이 train/test에 동시에 존재하는 누수를 막는다.
   - ③ class 수를 줄인다.
   - ④ 모든 class의 샘플 수를 같게 만든다.
   - **정답:** ②
   - **해설:** 동일 identity가 여러 partition에 들어가면 모델이 일반화가 아니라 얼굴 자체를 기억할 수 있다.

2. JSON의 face 필드에 대한 설명으로 옳은 것은?
   - ① expression target label
   - ② RGB pixel array
   - ③ OBJ mesh face connectivity
   - ④ optimizer state
   - **정답:** ③
   - **해설:** face는 f i j k 형태의 면 정보이며 primary MLP 입력은 3Dlandmark vertex다.

3. joint model에서 이미지에만 horizontal flip을 적용하면?
   - ① AUROC가 항상 1이 된다.
   - ② RGB와 landmark의 spatial correspondence가 깨진다.
   - ③ EfficientNet이 convolution을 수행하지 못한다.
   - ④ class 수가 감소한다.
   - **정답:** ②
   - **해설:** paired transform이 아니므로 두 modality가 서로 다른 geometry를 나타낸다.

### OX 문제

1. Macro F1은 class별 F1을 support 비율로 가중 평균한 값이다.
   - **정답:** X
   - **해설:** Macro F1은 각 class를 동일 가중치로 평균한다. support 가중 평균은 weighted F1이다.

2. Test set은 validation score가 가장 좋은 checkpoint를 고르는 데 사용해도 된다.
   - **정답:** X
   - **해설:** test는 최종 한 번의 generalization report에만 사용해야 한다.

3. 3D landmark를 centroid subtraction과 scale normalization하면 absolute translation과 scale nuisance가 줄어든다.
   - **정답:** O
   - **해설:** 중심과 스케일을 canonicalize하지만 상대적인 deformation은 보존한다.

### 단답형

1. class별 recall의 평균으로 정의되는 지표는?
   - **정답:** Balanced Accuracy
   - **해설:** Balanced Accuracy = 1/K Σ recall_k.

2. JSON의 v x y z 문자열을 [P,3] float tensor로 바꾸는 과정은?
   - **정답:** OBJ vertex parsing
   - **해설:** f i j k face 문자열은 vertex parsing 대상이 아니다.

3. 6×6 grid에 표시해야 하는 최소 정답·예측 정보는?
   - **정답:** ground-truth label, predicted label, confidence
   - **해설:** 이미지와 함께 correct/incorrect failure mode를 사람이 확인할 수 있어야 한다.

### 서술형

1. Vision-only EfficientNet-B0와 landmark-fused model을 공정하게 비교하는 실험 설계를 서술하라.
   - **모범 답안:** 두 모델에 동일한 subject-level split, seed, image preprocessing, optimizer, learning rate, epoch 수와 pretrained policy를 적용한다. Vision-only는 RGB branch만 사용하고, joint model은 같은 EfficientNet-B0 feature에 normalized 3D landmark MLP branch를 추가해 feature-level concatenation 후 projection한다. Validation Macro F1로 checkpoint를 선택하고, 선택된 checkpoint로 untouched test를 한 번 평가하여 Macro F1, Balanced Accuracy, Macro AUROC, class-wise PR curve를 비교한다. parameter count와 inference latency도 함께 기록한다.
   - **채점 포인트:** identity split, same protocol, modality 차이, test isolation, multiple metrics, efficiency report

2. Landmark branch의 spatial asymmetry metric을 정의하고 한계점을 설명하라.
   - **모범 답안:** 각 sample의 vertex를 centroid와 scale로 정규화한 뒤 좌우 midline을 기준으로 한쪽 point를 반사하고 반대편 point 집합과의 nearest-neighbor distance 평균을 계산한다. 값이 작을수록 좌우 형상이 대칭적이다. semantic left/right pairing index가 없으므로 nearest-neighbor pairing 가정에 의존하며, 후속 연구에서는 해부학적 correspondence로 검증해야 한다.
   - **채점 포인트:** normalization, reflection, distance, interpretation, limitation

3. 8시간 empirical validation schedule에서 기록해야 할 항목을 설명하라.
   - **모범 답안:** 시작/종료 wall-clock, completed epochs, device, seed, dataset manifest, split subject list, parameter count, best validation epoch/score, test sample 수와 latency, test Macro F1·Balanced Accuracy·AUROC·PR curve, 6×6 grid 경로를 기록한다. 8시간 budget 지정만으로 실행 완료를 주장하지 않고 runtime_seconds와 log를 근거로 보고한다.
   - **채점 포인트:** reproducibility metadata, epoch completion, split, metrics, latency, visualization, no fabricated result

## 9. 한 페이지 최종 요약

### 입력 → 표현 → 결합 → 평가 암기 순서

1. **입력**: RGB face crop I + OBJ vertex landmarks L
2. **전처리**: image 224×224 + ImageNet normalization; landmark centroid/scale normalization
3. **분할**: subject ID 기준 60/20/20, identity leakage 금지
4. **image encoder**: EfficientNet-B0 → h_img
5. **landmark encoder**: LayerNorm + MLP → h_lm
6. **fusion**: [h_img; h_lm] → Linear + LayerNorm + GELU + Dropout
7. **분류**: MLP head → K=7 class logits
8. **학습**: AdamW + Cross Entropy + cosine scheduler, 동일 seed/protocol
9. **평가**: Macro F1, Balanced Accuracy, Macro AUROC, class-wise PR
10. **분석**: asymmetry, geometric shift, parameter count, latency, 6×6 grid

### 핵심 수식

~~~text
L_norm = (L - mean(L)) / max(||L - mean(L)|| + eps)
h_img = EfficientNetB0(I)
h_lm  = MLP(L_norm)
h_fuse = Projection([h_img ; h_lm])
loss = CrossEntropy(logits, target)
BalancedAcc = mean_k Recall_k
MacroF1 = mean_k F1_k
~~~

### 실제 산출물

| 파일 | 의미 |
|---|---|
| dataset/drive_landmark/manifest.json | PNG–JSON paired manifest |
| dataset/drive_landmark/dataset_summary.json | subject/class/view count |
| dataset/face_experiments/best_vision.pt | vision-only checkpoint |
| dataset/face_experiments/best_joint.pt | landmark-fused checkpoint |
| metrics_vision.json, metrics_joint.json | history + final test metrics |
| predictions_vision.json, predictions_joint.json | sample-level GT/pred/probability |
| qualitative_grid_vision_6x6.png, qualitative_grid_joint_6x6.png | qualitative test visualization |
| comparison.json | baseline 대비 joint 개선량 및 efficiency summary |

## 이 장에서 가장 중요한 10가지

1. **EfficientNet-B0**는 edge deployment를 고려한 compact image backbone이다.
2. RGB만 쓰는 **vision-only baseline**과 RGB+landmark **joint model**을 동일 protocol에서 비교한다.
3. JSON의 3Dlandmark는 OBJ 문자열이므로 v x y z parser가 필요하다.
4. face는 mesh topology이며 primary MLP 입력과 구분한다.
5. Landmark는 centroid subtraction과 scale normalization으로 canonicalize한다.
6. 같은 identity가 여러 split에 들어가면 성능이 누수되므로 **identity-disjoint split**을 사용한다.
7. Joint model에서 image와 landmark에 서로 다른 spatial transform을 적용하면 정합성이 깨진다.
8. Validation으로 checkpoint를 선택하고 test는 마지막에 한 번만 평가한다.
9. **Macro F1, Balanced Accuracy, AUROC, PR curve**를 함께 보고한다.
10. **spatial asymmetry, geometric shift, latency, parameter count, 6×6 grid**를 수치 결과와 함께 보고한다.
