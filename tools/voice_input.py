import speech_recognition as sr

def voice_input(_arg: str = "") -> str:
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Скажите что-нибудь...")
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio, language="ru-RU")
        return text
    except sr.UnknownValueError:
        return "Не удалось распознать речь"
    except sr.RequestError as e:
        return f"Ошибка сервиса Google Speech Recognition; {e}"

TOOLS = {"voice_input": voice_input}
DESCRIPTION = "voice_input\n  Принимает аудиофайл и возвращает распознанный текст.\n"