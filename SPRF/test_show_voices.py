import pyttsx3
engine = pyttsx3.init()
voices = engine.getProperty('voices')
for v in voices:
    print(v.id)
