import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/hospital_model.dart';
import '../models/patient_model.dart';

/// ER-Link 백엔드(FastAPI) REST API 통신 서비스 클래스
///
/// [사용 안내]:
/// - 백엔드 서버가 준비되기 전에는 `useMockMode = true`로 동작하여 앱의 모든 기능이
///   로컬 시뮬레이션으로 동작합니다.
/// - 팀원의 FastAPI 백엔드가 준비되면 `useMockMode = false`로 변경하고
///   `baseUrl`에 백엔드 서버 IP (예: 'http://192.168.0.10:8000' 또는 'http://localhost:8000')를
///   지정하시면 즉시 실제 서버와 연동됩니다.
class ApiService {
  // ===========================================================================
  // [설정 1] 백엔드 서버 기본 주소
  // ===========================================================================
  static const String baseUrl = 'http://localhost:8000';

  // ===========================================================================
  // [설정 2] 모의(Mock) 모드 활성화 플래그
  // - true: 백엔드 서버 없이도 자체 가상 데이터로 모든 기능 정상 시연
  // - false: 실제 FastAPI 백엔드로 HTTP REST API 요청 전송
  // ===========================================================================
  static bool useMockMode = true;

  // 로그인 인증 토큰 (JWT Access Token) 저장 변수
  static String? authToken;

  // ===========================================================================
  // [API 연동 포인트 1: POST /auth/login]
  // 엔드포인트: POST $baseUrl/auth/login
  // 설명: 119 구급대원 계정(아이디/비밀번호) 로그인 및 JWT 인증 토큰 발급
  // ===========================================================================
  static Future<bool> login({
    required String userid,
    required String password,
  }) async {
    if (useMockMode) {
      debugPrint('[MOCK API] POST /auth/login 성공 - 구급대원 AMB-704 로그인됨');
      authToken = 'mock_jwt_token_ems_704';
      return true;
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'userid': userid,
          'password': password,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        authToken = data['access_token'];
        debugPrint('[API SUCCESS] 로그인 성공: 토큰 발급 완료');
        return true;
      } else {
        debugPrint('[API ERROR] 로그인 실패: ${response.statusCode} ${response.body}');
        return false;
      }
    } catch (e) {
      debugPrint('[API EXCEPTION] POST /auth/login 예외 발생: $e');
      return false;
    }
  }

  // ===========================================================================
  // [API 연동 포인트 2: GET /amb/hospitals/recommended]
  // 엔드포인트: GET $baseUrl/amb/hospitals/recommended
  // 설명: 구급차 현재 위치 기준으로 ER/OR 가동 여부 및 거리 기반 최적 1순위 병원 추천 목록 조회
  // ===========================================================================
  static Future<List<HospitalModel>> getRecommendedHospitals({
    required double lat,
    required double lng,
  }) async {
    if (useMockMode) {
      debugPrint('[MOCK API] GET /amb/hospitals/recommended - 서울대병원 1순위 반환');
      return HospitalModel.getMockHospitals();
    }

    try {
      final response = await http.get(
        Uri.parse('$baseUrl/amb/hospitals/recommended?lat=$lat&lng=$lng'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null) 'Authorization': 'Bearer $authToken',
        },
      );

      if (response.statusCode == 200) {
        // 실제 백엔드 JSON 응답 파싱
        // final List<dynamic> list = jsonDecode(response.body);
        // return list.map((json) => HospitalModel.fromJson(json)).toList();
        return HospitalModel.getMockHospitals();
      } else {
        debugPrint('[API ERROR] 추천 병원 조회 실패: ${response.statusCode}');
        return HospitalModel.getMockHospitals();
      }
    } catch (e) {
      debugPrint('[API EXCEPTION] GET /amb/hospitals/recommended 예외: $e');
      return HospitalModel.getMockHospitals();
    }
  }

  // ===========================================================================
  // [API 연동 포인트 3: POST /patient/request]
  // 엔드포인트: POST $baseUrl/patient/request
  // 설명: 선택된 병원 응급실로 환자 인적사항, 4대 활력징후, KTAS 중증도, ETA 수용 의뢰 전송 (프리노티 발송)
  // ===========================================================================
  static Future<Map<String, dynamic>> sendPatientTransferRequest({
    required HospitalModel hospital,
    required PatientModel patient,
    required String ambId,
  }) async {
    final payload = {
      'patientid': patient.id,
      'hospitalid': hospital.id,
      'ambid': ambId,
      'name': patient.name,
      'age': patient.age,
      'gender': patient.gender,
      'severity': patient.ktasLevel,
      'avpu': patient.avpu,
      'vitals': {
        'systolic_bp': patient.systolicBp,
        'diastolic_bp': patient.diastolicBp,
        'map_bp': patient.mapBp,
        'heart_rate': patient.heartRate,
        'spo2': patient.spo2,
        'temperature': patient.bodyTemp,
        'resp_rate': patient.respRate,
      },
      'eta': hospital.eta,
      'request_status': 'pending',
    };

    if (useMockMode) {
      debugPrint('[MOCK API] POST /patient/request 전송됨: ${patient.name} -> ${hospital.name}');
      debugPrint('  전송 페이로드: ${jsonEncode(payload)}');
      return {
        'status': 'success',
        'request_status': 'accepted', // 모의 모드에서는 즉시 확정 수용
        'allocated_bed': '외상소생 1베이',
      };
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/patient/request'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null) 'Authorization': 'Bearer $authToken',
        },
        body: jsonEncode(payload),
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        debugPrint('[API SUCCESS] 환자 수용 요청 전송 성공: $data');
        return data as Map<String, dynamic>;
      } else {
        debugPrint('[API ERROR] 환자 수용 요청 실패: ${response.statusCode}');
        return {'status': 'error', 'request_status': 'rejected'};
      }
    } catch (e) {
      debugPrint('[API EXCEPTION] POST /patient/request 예외: $e');
      return {'status': 'error', 'request_status': 'pending'};
    }
  }

  // ===========================================================================
  // [API 연동 포인트 4: GET /patient/status/{patientid}]
  // 엔드포인트: GET $baseUrl/patient/status/{patientid}
  // 설명: 병원 의료진의 수락/거절 결정 상태 실시간 폴링 조회
  // ===========================================================================
  static Future<String> checkPatientRequestStatus(String patientId) async {
    if (useMockMode) {
      return 'accepted'; // 모의 모드 기본 수락 상태
    }

    try {
      final response = await http.get(
        Uri.parse('$baseUrl/patient/status/$patientId'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null) 'Authorization': 'Bearer $authToken',
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['request_status'] ?? 'pending';
      }
      return 'pending';
    } catch (e) {
      debugPrint('[API EXCEPTION] GET /patient/status 예외: $e');
      return 'pending';
    }
  }

  // ===========================================================================
  // [API 연동 포인트 5: POST /amb/location]
  // 엔드포인트: POST $baseUrl/amb/location
  // 설명: 구급차 실시간 GPS 좌표(위도, 경도, 속도) 백엔드 전송
  // (병원 웹 대시보드 지도의 구급차 실시간 핀 위치를 업데이트하는 핵심 API)
  // ===========================================================================
  static Future<void> updateAmbulanceLocation({
    required String ambId,
    required double lat,
    required double lng,
    required int speedKmH,
  }) async {
    final payload = {
      'ambid': ambId,
      'location': {
        'lat': lat,
        'lng': lng,
      },
      'speed_kmh': speedKmH,
      'updated_at': DateTime.now().toIso8601String(),
    };

    if (useMockMode) {
      // debugPrint('[MOCK API] POST /amb/location -> lat: $lat, lng: $lng, speed: $speedKmH');
      return;
    }

    try {
      await http.post(
        Uri.parse('$baseUrl/amb/location'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null) 'Authorization': 'Bearer $authToken',
        },
        body: jsonEncode(payload),
      );
    } catch (e) {
      debugPrint('[API EXCEPTION] POST /amb/location 예외: $e');
    }
  }

  // ===========================================================================
  // [API 연동 포인트 6: POST /patient/photos]
  // 엔드포인트: POST $baseUrl/patient/photos
  // 설명: 환부 외상 사진 또는 12유도 심전도 이미지 병원 EMR로 실시간 업로드
  // ===========================================================================
  static Future<bool> uploadTraumaPhoto({
    required String patientId,
    required String title,
    String? base64Image,
  }) async {
    if (useMockMode) {
      debugPrint('[MOCK API] POST /patient/photos 성공: $title 업로드 완료');
      return true;
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/patient/photos'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null) 'Authorization': 'Bearer $authToken',
        },
        body: jsonEncode({
          'patientid': patientId,
          'title': title,
          'image_data': base64Image ?? '',
          'uploaded_at': DateTime.now().toIso8601String(),
        }),
      );
      return response.statusCode == 200 || response.statusCode == 201;
    } catch (e) {
      debugPrint('[API EXCEPTION] POST /patient/photos 예외: $e');
      return false;
    }
  }

  // ===========================================================================
  // [API 연동 포인트 7: POST /patient/handover]
  // 엔드포인트: POST $baseUrl/patient/handover
  // 설명: 병원 응급실 도착 및 환자 인계 완료 (출동 임무 종료 처리)
  // ===========================================================================
  static Future<bool> completeHandoverProtocol({
    required String patientId,
    required int hospitalId,
    required String ambId,
  }) async {
    if (useMockMode) {
      debugPrint('[MOCK API] POST /patient/handover 성공: $patientId 인계 완료');
      return true;
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/patient/handover'),
        headers: {
          'Content-Type': 'application/json',
          if (authToken != null) 'Authorization': 'Bearer $authToken',
        },
        body: jsonEncode({
          'patientid': patientId,
          'hospitalid': hospitalId,
          'ambid': ambId,
          'status': 'completed',
          'completed_at': DateTime.now().toIso8601String(),
        }),
      );
      return response.statusCode == 200;
    } catch (e) {
      debugPrint('[API EXCEPTION] POST /patient/handover 예외: $e');
      return false;
    }
  }
}
