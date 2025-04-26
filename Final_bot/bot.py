import telebot
from config import TOKEN
from rembg import remove
from PIL import Image, ImageColor
from io import BytesIO
import os


bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.send_message(message.chat.id, '''Привет! Отправь мне картинку, и я помогу поменять или удалить фон.''')
    bot.send_message(message.chat.id, '''Что ты хочешь, чтобы я сделал?
Я могу:
удалить фон /delete
поменять фон на один цвет /color
поменять фон на твой /my_fon
Сначала отправь картинку, потом ответь на картинку командой.
С командой my_fon надо отправить 2 картинки:
сначала картинку, у которой вы хотите поменять фон ,
потом картинку, у которой вы хотите взять фон,
и ответить на картинку, у которой вы хотите поменять фон, командой my_fon.\n
ФОТО НЕ ДОЛЖНО БЫТЬ ДОКУМЕНТОМ!''')


@bot.message_handler(commands=['delete'])
def delete_background(message):
    try:
        if not message.reply_to_message or not message.reply_to_message.photo:
            bot.reply_to(message, "Пожалуйста, ответьте командой `/delete` на сообщение с фото.")
            return

        file_id = message.reply_to_message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        os.makedirs('downloads', exist_ok=True)

        input_path = os.path.join('downloads', f'{file_id}_input.jpg')
        with open(input_path, 'wb') as f:
            f.write(downloaded_file)

        with Image.open(input_path) as img:
            output_img = remove(img)  
            output_path = os.path.join('downloads', f'{file_id}_nobg.png')
            output_img.save(output_path)

        with open(output_path, 'rb') as f:
            bot.send_photo(message.chat.id, f, caption="Фон успешно удалён!")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")
        print(f"Error in delete_background: {e}")


@bot.message_handler(commands=['color'])
def change_background(message):
    try:
        # Проверка, что команда отправлена в ответ на фото
        if not message.reply_to_message or not message.reply_to_message.photo:
            bot.reply_to(message, "Пожалуйста, ответьте командой `/color <цвет>` на сообщение с фото.")
            return

        # Получение цвета из команды
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "Пожалуйста, укажите цвет. Пример: `/color #00ff00` или `/color red`.")
            return

        color_input = args[1].strip()

        # Попытка преобразовать цвет в RGB
        try:
            color = ImageColor.getrgb(color_input.lower())
        except ValueError:
            bot.reply_to(
                message,
                "Неверный формат цвета.\n"
                "Поддерживаются:\n"
                "Названия: `red`, `green`, `blue` и др.\n"
                "HEX: `#ff0000`\n"
                "RGB: `rgb(255,0,0)` или `255,0,0`"
            )
            return

        # Получение изображения от пользователя
        file_id = message.reply_to_message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Сохранение оригинала
        os.makedirs('downloads', exist_ok=True)
        input_path = os.path.join('downloads', f'{file_id}_input.jpg')
        with open(input_path, 'wb') as f:
            f.write(downloaded_file)

        # Удаление фона
        with Image.open(input_path) as img:
            img_nobg = remove(img.convert("RGBA"))

            # Создание цветного фона
            bg = Image.new("RGBA", img_nobg.size, color + (255,))
            combined = Image.alpha_composite(bg, img_nobg)

            # Сохранение результата
            output_path = os.path.join('downloads', f'{file_id}_colored.jpg')
            combined.convert("RGB").save(output_path, "JPEG")

        # Отправка результата
        with open(output_path, 'rb') as f:
            bot.send_photo(message.chat.id, f, caption=f"Фон заменён на {color_input}!")

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {str(e)}")
        print(f"Error in replace_background_color: {e}")

user_backgrounds = {}

@bot.message_handler(content_types=['photo', 'document'])
def handle_background(message):
    try:
        if message.photo:
            file_info = bot.get_file(message.photo[-1].file_id)
            bg_bytes = bot.download_file(file_info.file_path)
            
        elif message.document:
            if not message.document.mime_type.startswith('image/'):
                bot.reply_to(message, "Пожалуйста, отправьте изображение, которое будет использоваться в качестве фона.")
                return
            file_info = bot.get_file(message.document.file_id)
            bg_bytes = bot.download_file(file_info.file_path)
        else:
            return

        user_backgrounds[message.chat.id] = bg_bytes
        bot.reply_to(message, "Картинка сохранена!")

    except Exception as e:
        bot.reply_to(message, f"Ошибка при сохранении фона: {str(e)}")

@bot.message_handler(commands=['my_fon'])
def handle_removebg(message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        bot.reply_to(message, "Пожалуйста, отправьте фото, с которого нужно убрать фон, первым, и ответьте на это фото командой `/my_fon`.")
        return

    try:
        file_info = bot.get_file(message.reply_to_message.photo[-1].file_id)
        main_photo = bot.download_file(file_info.file_path)
        input_image = Image.open(BytesIO(main_photo))
        output_image = remove(input_image) 

        if message.chat.id in user_backgrounds:
            try:
                new_bg = Image.open(BytesIO(user_backgrounds[message.chat.id]))
                new_bg = new_bg.resize(output_image.size)
                
                if output_image.mode == 'RGBA':
                    output_image = Image.alpha_composite(new_bg.convert('RGBA'), output_image)
                else:
                    output_image.paste(new_bg, (0, 0))
                
                del user_backgrounds[message.chat.id]
            except Exception as e:
                print(f"Ошибка при наложении фона: {e}")
                bot.reply_to(message, "Не удалось наложить фон. Возвращаю фото без фона.")

        output_bytes = BytesIO()
        output_image.save(output_bytes, format='PNG')
        output_bytes.seek(0)
        
        bot.send_photo(message.chat.id, output_bytes, caption="Результат обработки.")

    except Exception as e:
        bot.reply_to(message, f"Ошибка при обработке: {str(e)}")

bot.infinity_polling()