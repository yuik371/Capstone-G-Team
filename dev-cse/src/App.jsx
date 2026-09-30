import React from 'react';

const EmergencyDispatchPage = () => {
  return (
    <div className="min-h-screen bg-[#fcfcfc] relative flex flex-col font-sans text-gray-900 overflow-hidden">
      {/* 상단 헤더 */}
      <header className="w-full p-6 md:px-12 md:py-8 flex justify-between items-center absolute top-0 left-0 z-10">
        {/* 좌측 로고 */}
        <div className="w-10 h-10 bg-[#e31b23] rounded-lg flex justify-center items-center shadow-sm">
          <svg 
            xmlns="http://www.w3.org/2000/svg" 
            viewBox="0 0 24 24" 
            fill="currentColor" 
            className="w-6 h-6 text-white"
          >
            <path fillRule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zM12.75 9a.75.75 0 00-1.5 0v2.25H9a.75.75 0 000 1.5h2.25V15a.75.75 0 001.5 0v-2.25H15a.75.75 0 000-1.5h-2.25V9z" clipRule="evenodd" />
          </svg>
        </div>

        {/* 우측 콘솔 체험 버튼 */}
        <button className="bg-[#e31b23] hover:bg-red-700 transition-colors text-white px-6 py-2.5 rounded-full text-sm font-semibold flex items-center gap-2">
          콘솔 체험 <span>→</span>
        </button>
      </header>

      {/* 메인 콘텐츠 영역 */}
      <main className="flex-1 w-full h-full flex mt-32 px-10 md:px-32 lg:px-48 relative max-w-7xl mx-auto">
        
        {/* 좌측 영역: 라이브 표시 및 상태 배지 */}
        <div className="w-1/3 flex flex-col pt-12 relative">
          {/* LIVE 텍스트 */}
          <div className="absolute top-0 left-0 flex items-center gap-2 text-[11px] font-bold text-gray-400 tracking-[0.2em]">
            <div className="w-2 h-2 rounded-full bg-[#e31b23]"></div>
            LIVE - EMERGENCY DISPATCH
          </div>

          {/* 배지 리스트 */}
          <div className="flex flex-col gap-3 mt-40">
            <span className="bg-[#f2f2f2] text-gray-700 px-4 py-2 rounded-full w-max text-sm font-medium shadow-sm">
              중증도 87%
            </span>
            <span className="bg-[#f2f2f2] text-gray-700 px-4 py-2 rounded-full w-max text-sm font-medium shadow-sm">
              외상 사진 3장
            </span>
            <span className="bg-[#f2f2f2] text-gray-700 px-4 py-2 rounded-full w-max text-sm font-medium shadow-sm">
              ETA 8분
            </span>
          </div>
        </div>

        {/* 우측 영역: 메인 타이포그래피 */}
        <div className="w-2/3 flex flex-col justify-center pl-10 pt-24">
          <div className="text-[#e31b23] font-semibold text-sm mb-4 tracking-wide">
            02 - 수용 요청
          </div>
          <h1 className="text-[3.5rem] md:text-[4rem] leading-[1.15] font-bold text-gray-900 tracking-tight">
            도착 전에 확인하는<br/>
            중증도와 <span className="text-[#e31b23] italic font-serif">Trauma</span>
          </h1>
          <p className="mt-6 text-gray-500 text-lg max-w-md word-keep">
            중증도 예측·필요 진료과·외상 사진을 수용 요청과 함께 받습니다.
          </p>
        </div>
      </main>

      {/* 하단 스크롤 마우스 아이콘 */}
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2 opacity-50">
        <div className="w-6 h-10 border-2 border-gray-400 rounded-full flex justify-center pt-2">
          <div className="w-1 h-2 bg-gray-400 rounded-full animate-bounce"></div>
        </div>
      </div>
    </div>
  );
};

export default EmergencyDispatchPage;