@echo off
:: Script per automazione Git: Add, Commit e Push

echo Eseguendo git add .
git add .

:: Chiede il messaggio di commit
set /p "msg=Inserisci messaggio di commit (premi INVIO per 'aggiornamento rapido'): "
if "%msg%"=="" set msg=aggiornamento rapido

echo.
echo Eseguendo git commit...
git commit -m "%msg%"

echo.
echo Eseguendo git push...
git push origin main

echo.
echo Fatto!
pause
