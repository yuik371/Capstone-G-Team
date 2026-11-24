# 상처 유형-중증도 라벨링 프로토콜

## 목적과 경계

이 데이터셋의 `abrasions`, `bruises`, `cut`, `stab`은 **상처 외관 유형** 라벨이다.
이는 KTAS 1-5 등급이나 진단명이 아니다. 동일한 상처 유형도 출혈, 의식, 호흡,
혈역학, 손상 기전, 통증, 해부학적 부위에 따라 서로 다른 중증도를 가질 수 있다.

따라서 EfficientNet-B0의 출력은 중증도 모델의 영상 특징 또는 보조 관찰값으로만
사용한다. `wound_type -> KTAS` 고정 매핑이나 이미지 단독 자동 KTAS 라벨 생성은
금지한다.

## 근거와 라벨 권한

- 병원 내 KTAS는 「한국 응급환자 중증도 분류기준」의 대상·시행주체에 맞춰
  의사, 간호사 또는 1급 응급구조사 등 자격을 가진 임상 검토자가 부여한다.
- 구급차 이송 시나리오는 별도의 「한국 병원 전 응급환자 중증도 분류기준」을
  적용한다. 병원 내 KTAS 라벨을 병원 전 라벨로 임의 변환하지 않는다.
- 기준 문서의 실제 항목·코드 적용은 교육을 이수한 검토자가 원문을 확인한다.
  프로젝트 구성원은 원문 검토나 자문 전에는 `clinical_ktas_level`을 채우지 않는다.

## 생성된 manifest와 입력 항목

다음 명령은 기존 crop의 상처 유형 라벨을 보존한 `dataset/triage_manifest.csv`를
만든다. 새 manifest의 KTAS 칸은 의도적으로 비어 있다.

```powershell
cd dev-YuIK
..\.venv\Scripts\python.exe -m emergency_cdss.scripts.create_triage_manifest `
  --image-root dataset --output dataset/triage_manifest.csv
```

임상 검토자는 최소한 다음 정보를 같은 `deidentified_case_id`에 연결한다.

1. 주호소, 손상 기전, 부위, 연령군, 통증 점수
2. 의식 상태, 호흡 상태, 혈역학 상태, 활동성 출혈 및 지혈 여부
3. 신경혈관 손상 및 기도 우려
4. 최종 KTAS 등급, 해당 기준 코드, 검토자 식별자·역할·검토시각

직접 식별정보(성명, 전화번호, 주민등록번호 등)는 manifest에 저장하지 않는다.

## 이중 라벨링과 품질관리

1. 두 명의 자격 있는 검토자가 독립적으로 라벨한다.
2. 불일치 사례는 제3의 검토자가 조정하고 `adjudication_status`에 남긴다.
3. `ktas_reference_code`와 필요한 입력이 비어 있으면 학습 대상에서 제외한다.
4. 분할은 crop이나 이미지가 아니라 `deidentified_case_id` 단위로 시행한다.
5. KTAS 분포, 검토자 간 Cohen's kappa, 클래스별 macro-F1/recall, calibration을
   보고한다. 안전상 KTAS 1-2의 recall과 under-triage 비율을 우선 지표로 둔다.

검토 후 아래 명령으로 누락 항목을 검사한다.

```powershell
..\.venv\Scripts\python.exe -m emergency_cdss.scripts.create_triage_manifest `
  --validate dataset/triage_manifest.csv
```

## 학습 데이터 구성

중증도 학습 샘플은 다음처럼 구성한다. 영상 branch와 structured branch를 late
fusion하되, 최종 예측은 임상 의사결정을 대체하지 않는 보조 결과로 제한한다.

```text
wound image -> EfficientNet-B0 -> wound embedding / wound-type probability
clinical fields -> encoded structured features
                                      -> fusion classifier -> KTAS research label
```

원 데이터에 임상 입력과 전문가 KTAS 정답이 아직 없으므로, 현 시점에는 KTAS
모델의 학습·평가 수치 또는 중증도→자원 매핑을 주장할 수 없다.
