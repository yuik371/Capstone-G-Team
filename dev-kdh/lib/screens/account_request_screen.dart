import 'package:flutter/material.dart';
import '../config/app_theme.dart';
import '../services/api_service.dart';

class AccountRequestScreen extends StatefulWidget {
  final String? initialUserId;

  const AccountRequestScreen({super.key, this.initialUserId});

  @override
  State<AccountRequestScreen> createState() => _AccountRequestScreenState();
}

class _AccountRequestScreenState extends State<AccountRequestScreen> {
  final _formKey = GlobalKey<FormState>();

  // If not logged in yet, allow credentials input to authenticate on-the-fly
  late final TextEditingController _userIdController;
  final _passwordController = TextEditingController();

  // Account Request form controllers (119 구급대 전용)
  final _accountNameController = TextEditingController(text: '종로소방서 704호 특수구급대');
  final _applicantNameController = TextEditingController(text: '김민우');
  final _positionController = TextEditingController(text: '1급 응급구조사 (소방교)');
  final _phoneController = TextEditingController(text: '010-1190-7040');
  final _reasonController = TextEditingController(
    text: '응급환자 골든타임 사수를 위한 지역 병원 병상 & 이동동선 통합 관제 및 긴급 구조콜(amb/emergency/call) 권한 승인 요청',
  );

  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _userIdController = TextEditingController(
      text: ApiService.currentUserId ?? widget.initialUserId ?? '',
    );
  }

  @override
  void dispose() {
    _userIdController.dispose();
    _passwordController.dispose();
    _accountNameController.dispose();
    _applicantNameController.dispose();
    _positionController.dispose();
    _phoneController.dispose();
    _reasonController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    // 1. If not logged in yet, login first to obtain JWT Bearer Token
    if (ApiService.authToken == null || ApiService.authToken!.isEmpty) {
      final loginId = _userIdController.text.trim();
      final loginPw = _passwordController.text;

      if (loginId.isEmpty || loginPw.isEmpty) {
        setState(() {
          _isLoading = false;
          _errorMessage = '계정 발급 요청을 전송하려면 먼저 로그인 아이디와 비밀번호를 입력해야 합니다.';
        });
        return;
      }

      final loginResult = await ApiService.login(userid: loginId, password: loginPw);
      if (!loginResult.success) {
        if (!mounted) return;
        setState(() {
          _isLoading = false;
          _errorMessage = '로그인 인증 실패: ${loginResult.message}';
        });
        return;
      }
    }

    // 2. Submit Account Link Request (POST /auth/link/requests, account_type="amb")
    final result = await ApiService.requestAccountLink(
      accountType: 'amb',
      accountName: _accountNameController.text.trim(),
      applicantName: _applicantNameController.text.trim(),
      position: _positionController.text.trim(),
      phone: _phoneController.text.trim(),
      reason: _reasonController.text.trim(),
    );

    if (!mounted) return;

    setState(() {
      _isLoading = false;
    });

    if (result.success) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (ctx) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Row(
            children: [
              Icon(Icons.check_circle, color: Color(0xFF059669), size: 24),
              SizedBox(width: 8),
              Text(
                '발급 요청 접수 완료',
                style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
              ),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                result.message,
                style: const TextStyle(fontSize: 13, height: 1.5, color: Color(0xFF374151)),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF9FAFB),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildSummaryRow('신청 유형', '119 구조대원 (amb)'),
                    _buildSummaryRow('소속 명칭', _accountNameController.text.trim()),
                    _buildSummaryRow('신청자', _applicantNameController.text.trim()),
                    _buildSummaryRow('직책/직급', _positionController.text.trim()),
                    _buildSummaryRow('연락처', _phoneController.text.trim()),
                  ],
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                '※ 관리자가 요청을 수락하면 구조대원 권한이 부여되며, 즉시 긴급 구조콜(/amb/emergency/call)을 사용할 수 있습니다.',
                style: TextStyle(fontSize: 11, color: Color(0xFF6B7280), height: 1.4),
              ),
            ],
          ),
          actions: [
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryRed,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: () {
                Navigator.pop(ctx); // Close dialog
                Navigator.pop(context); // Return to previous screen
              },
              child: const Text('확인', style: TextStyle(fontWeight: FontWeight.w800)),
            ),
          ],
        ),
      );
    } else {
      setState(() {
        _errorMessage = result.message;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.error_outline, color: Colors.white, size: 20),
              const SizedBox(width: 10),
              Expanded(child: Text(result.message)),
            ],
          ),
          backgroundColor: AppTheme.primaryRed,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  Widget _buildSummaryRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 70,
            child: Text(
              label,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFF6B7280)),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: Color(0xFF1F2937)),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isLoggedIn = ApiService.authToken != null && ApiService.authToken!.isNotEmpty;

    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text(
          '구조대원 권한 승인 신청 (AUTH LINK)',
          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Color(0xFF1F2937)),
        ),
        backgroundColor: Colors.white,
        elevation: 0.5,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: Color(0xFF1F2937), size: 18),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 540),
              child: Column(
                children: [
                  _buildHeaderBadge(),
                  const SizedBox(height: 16),
                  _buildFormCard(context, isLoggedIn),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF2F2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFECACA)),
      ),
      child: const Row(
        children: [
          Icon(Icons.shield_outlined, color: AppTheme.primaryRed, size: 24),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '구조대원 접근 권한 승인 안내',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.primaryRed,
                  ),
                ),
                SizedBox(height: 2),
                Text(
                  '응급구조 콜(/amb/emergency/call) 및 환자 이송 API는 소속 인증이 완료된 구조대원 계정만 호출할 수 있습니다.',
                  style: TextStyle(
                    fontSize: 11,
                    color: Color(0xFF7F1D1D),
                    height: 1.35,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFormCard(BuildContext context, bool isLoggedIn) {
    return Container(
      padding: const EdgeInsets.all(26),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE5E7EB)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 14,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Title
            Row(
              children: [
                Container(
                  width: 4,
                  height: 18,
                  decoration: BoxDecoration(
                    color: AppTheme.primaryRed,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 8),
                const Text(
                  '소속 기관 및 대원 정보 입력',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w900,
                    color: Color(0xFF111827),
                  ),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: isLoggedIn ? const Color(0xFFECFDF5) : const Color(0xFFFFFBEB),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: isLoggedIn ? const Color(0xFFA7F3D0) : const Color(0xFFFDE68A),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        isLoggedIn ? Icons.verified : Icons.lock_clock,
                        color: isLoggedIn ? const Color(0xFF059669) : const Color(0xFFD97706),
                        size: 12,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        isLoggedIn ? 'JWT 인증됨' : '로그인 필요',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          color: isLoggedIn ? const Color(0xFF059669) : const Color(0xFFD97706),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Error Banner
            if (_errorMessage != null) ...[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFEF2F2),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFFECACA)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline, color: Color(0xFF991B1B), size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _errorMessage!,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFF991B1B),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],

            // If not logged in, prompt credentials
            if (!isLoggedIn) ...[
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFFF9FAFB),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFFE5E7EB)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.account_circle_outlined, size: 16, color: Color(0xFF374151)),
                        SizedBox(width: 6),
                        Text(
                          '신청자 계정 로그인 (JWT 발급용)',
                          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: Color(0xFF374151)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _userIdController,
                      decoration: _inputDecoration('아이디 (USERID)', Icons.badge_outlined),
                      validator: (v) => (v == null || v.trim().isEmpty) ? '아이디를 입력하세요' : null,
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _passwordController,
                      obscureText: true,
                      decoration: _inputDecoration('비밀번호 (PASSWORD)', Icons.lock_outline),
                      validator: (v) => (v == null || v.isEmpty) ? '비밀번호를 입력하세요' : null,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
            ],

            // 1. Ambulance Unit Name
            const Text(
              '소속 소방서 / 구급대 명칭 (UNIT NAME)',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
            ),
            const SizedBox(height: 6),
            TextFormField(
              controller: _accountNameController,
              decoration: _inputDecoration('예: 종로소방서 704호 특수구급대', Icons.business_outlined),
              validator: (v) => (v == null || v.trim().isEmpty) ? '소속 명칭을 입력하세요' : null,
            ),
            const SizedBox(height: 14),

            // 2. Applicant Name & Position
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '신청 대원 성명',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
                      ),
                      const SizedBox(height: 6),
                      TextFormField(
                        controller: _applicantNameController,
                        decoration: _inputDecoration('성명 입력', Icons.person_outline),
                        validator: (v) => (v == null || v.trim().isEmpty) ? '성명을 입력하세요' : null,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '직책 / 직급',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
                      ),
                      const SizedBox(height: 6),
                      TextFormField(
                        controller: _positionController,
                        decoration: _inputDecoration('예: 1급 응급구조사 (소방교)', Icons.work_outline),
                        validator: (v) => (v == null || v.trim().isEmpty) ? '직책을 입력하세요' : null,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),

            // 3. Phone
            const Text(
              '대원 연락처 (PHONE)',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
            ),
            const SizedBox(height: 6),
            TextFormField(
              controller: _phoneController,
              keyboardType: TextInputType.phone,
              decoration: _inputDecoration('예: 010-1190-7040 (최소 8자 이상)', Icons.phone_outlined),
              validator: (v) {
                if (v == null || v.trim().isEmpty) return '연락처를 입력하세요';
                if (v.trim().length < 8) return '연락처는 최소 8자 이상이어야 합니다';
                return null;
              },
            ),
            const SizedBox(height: 14),

            // 4. Reason
            const Text(
              '신청 사유 (REASON)',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF374151)),
            ),
            const SizedBox(height: 6),
            TextFormField(
              controller: _reasonController,
              maxLines: 3,
              decoration: InputDecoration(
                hintText: '구조대원 권한 신청 사유를 구체적으로 작성해 주세요',
                hintStyle: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF)),
                filled: true,
                fillColor: const Color(0xFFF9FAFB),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppTheme.primaryRed, width: 1.5)),
              ),
              validator: (v) {
                if (v == null || v.trim().isEmpty) return '신청 사유를 입력하세요';
                if (v.trim().length < 5) return '사유를 5자 이상 상세히 입력하세요';
                return null;
              },
            ),
            const SizedBox(height: 22),

            // Submit Button
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryRed,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 15),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
              onPressed: _isLoading ? null : _handleSubmit,
              child: _isLoading
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2.5),
                    )
                  : const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.send, size: 18),
                        SizedBox(width: 8),
                        Text(
                          '구조대원 권한 신청 제출 (SUBMIT REQUEST)',
                          style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900),
                        ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }

  InputDecoration _inputDecoration(String hint, IconData icon) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF)),
      prefixIcon: Icon(icon, color: const Color(0xFF6B7280), size: 18),
      filled: true,
      fillColor: const Color(0xFFF9FAFB),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFFE5E7EB))),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: AppTheme.primaryRed, width: 1.5)),
    );
  }
}
