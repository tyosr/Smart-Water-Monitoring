@echo off
chcp 65001 >nul
echo 💧 Système de Surveillance du Niveau d'Eau
echo ===========================================
echo.

REM Vérifier si l'environnement virtuel existe
if exist "venv\Scripts\activate.bat" (
    echo Activation de l'environnement virtuel...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️ Environnement virtuel non trouvé, utilisation de Python système
)

echo.
echo Démarrage du serveur Flask...
start "Flask Server" cmd /k "python app.py"

echo.
echo Attente du serveur (3 secondes)...
timeout /t 3 /nobreak >nul

echo.
echo Démarrage du lecteur Arduino (mode test)...
start "Arduino Reader" cmd /k "python arduino_reader.py --test"

echo.
echo ===========================================
echo 🚀 Services démarrés!
echo 📊 Dashboard: http://127.0.0.1:5000
echo ===========================================
echo.
echo Appuyez sur une touche pour ouvrir le navigateur...
pause >nul

start http://127.0.0.1:5000
