# Fake imghdr module to prevent ModuleNotFoundError on Render
# This is safe because we don't send images, so 'imghdr.what()' is not used.

def what(file, h=None):
    return None  # Не можем определить тип — возвращаем None

# Псевдо-переменная, как в оригинальном модуле
tests = []
