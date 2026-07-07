@echo off
chcp 65001 > nul
echo ===================================================
echo 🚀 GITHUB-GA KODNI YUKLASH TIZIMI
echo ===================================================
echo.

:: Git borligini tekshirish
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Tizimda GIT o'rnatilmagan! Iltimos, Git-ni o'rnating.
    pause
    exit /b
)

:: Git repozitoriyasini ochish
if not exist .git (
    echo 📂 Git repozitoriyasi yaratilmoqda...
    git init
)

:: Fayllarni qo'shish
echo ➕ Fayllar ro'yxatga olinmoqda...
git add .

:: Commit yaratish
echo 💾 Commit qilinmoqda...
git commit -m "Telegram multiplayer game bot deployment"

echo.
echo ---------------------------------------------------
echo ✅ Mahalliy kompyuterda Git sozlandi!
echo ---------------------------------------------------
echo.
echo Endi GitHub saytida yangi bo'sh repozitoriy yarating.
set /p github_url="GitHub repozitoriyingiz havolasini kiriting (https://github.com/username/repo.git): "

if "%github_url%"=="" (
    echo ❌ Havola kiritilmadi. Jarayon bekor qilindi.
    pause
    exit /b
)

:: Masofaviy serverni ulash va yuklash
git remote remove origin >nul 2>nul
git remote add origin %github_url%
git branch -M main
echo.
echo 📤 Kod GitHub-ga yuklanmoqda...
git push -u origin main

echo.
echo ===================================================
echo 🎉 TUGALLANDI! Endi Render.com saytida ushbu repozitoriyga ulaning.
echo ===================================================
pause
