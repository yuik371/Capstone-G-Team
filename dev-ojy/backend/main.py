from fastapi import FastAPI,Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, hospital, control,admin, amb

app = FastAPI(title="응급실 관제 시스템")

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(hospital.router, prefix="/hospital", tags=["Hospital"], dependencies=[Depends(auth.get_current_user)])
app.include_router(control.router, prefix="/control", tags=["Control"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"], dependencies=[Depends(auth.get_current_user)])
app.include_router(amb.router, prefix="/amb", tags=["Amb"], dependencies=[Depends(auth.get_current_user)])

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","http://localhost:8000", "https://er-capstone-g.onrender.com"],
                   allow_credentials=True, allow_methods=["GET","POST","PUT","PATCH","DELETE"], allow_headers=["Authorization", "Content-Type"])