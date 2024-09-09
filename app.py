from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from PIL import Image, ImageEnhance
import numpy as np
import cv2
import os
import io
import requests  # Import the requests library

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure the upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def save_image(image, filename):
    if image.mode == 'RGBA':
        filename = os.path.splitext(filename)[0] + '.png'
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(path, format='PNG')
    else:
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(path, format='JPEG')
    return filename

def image_filter(image, filter_type):
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    
    if filter_type == 'CONTOUR':
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        image_cv = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    elif filter_type == 'BLUR':
        image_cv = cv2.GaussianBlur(image_cv, (15, 15), 0)
    elif filter_type == 'SHARPEN':
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        image_cv = cv2.filter2D(image_cv, -1, kernel)
    elif filter_type == 'EDGE_ENHANCE':
        kernel = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])
        image_cv = cv2.filter2D(image_cv, -1, kernel)
    elif filter_type == 'EMBOSS':
        kernel = np.array([[0, -1, -1], [1, 0, -1], [1, 1, 0]])
        image_cv = cv2.filter2D(image_cv, -1, kernel)
    elif filter_type == 'SEPIA':
        kernel = np.array([[0.272, 0.534, 0.131], [0.349, 0.686, 0.168], [0.393, 0.769, 0.189]])
        image_cv = cv2.transform(image_cv, kernel)
        image_cv = np.clip(image_cv, 0, 255)
    elif filter_type == 'COOL':
        increase_blue = np.array([255, 0, 0], dtype='uint8')
        image_cv = cv2.add(image_cv, increase_blue)
    elif filter_type == 'WARM':
        increase_red = np.array([0, 0, 255], dtype='uint8')
        image_cv = cv2.add(image_cv, increase_red)
    elif filter_type == 'BRIGHTEN':
        image_cv = cv2.convertScaleAbs(image_cv, alpha=1.2, beta=30)
    elif filter_type == 'VIBRANT':
        hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
        hsv[..., 1] = hsv[..., 1] * 1.5
        image_cv = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    image_pil = Image.fromarray(cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB))
    return image_pil

def remove_background(image, api_key, bg_color=None, no_bg_color=False):
    # Save the image to a temporary file to send to the API
    temp_image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_image.png')
    image.save(temp_image_path, format='PNG')

    # Call the remove.bg API
    with open(temp_image_path, 'rb') as img_file:
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            files={'image_file': img_file},
            data={'size': 'auto'},
            headers={'X-Api-Key': api_key}
        )
    
    if response.status_code == requests.codes.ok:
        result_image = Image.open(io.BytesIO(response.content))
        
        if bg_color and not no_bg_color:
            if result_image.mode in ('RGBA', 'LA') or (result_image.mode == 'P' and 'transparency' in result_image.info):
                background = Image.new('RGBA', result_image.size, bg_color)
                result_image = Image.alpha_composite(background, result_image)
                result_image = result_image.convert("RGB")

        return result_image
    else:
        print("Error:", response.status_code, response.text)
        return image  # Return the original image if API call fails

def image_enhance(image, enhancement_type, factor):
    enhancer = None

    if enhancement_type == 'BRIGHTNESS':
        enhancer = ImageEnhance.Brightness(image)
    elif enhancement_type == 'CONTRAST':
        enhancer = ImageEnhance.Contrast(image)
    elif enhancement_type == 'SHARPNESS':
        enhancer = ImageEnhance.Sharpness(image)

    if enhancer is not None:
        enhanced_image = enhancer.enhance(factor)
        return enhanced_image
    else:
        return image

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['image']
        operation = request.form.get('operation')
        image = Image.open(file.stream)

        if operation == 'filter':
            filter_type = request.form.get('filter_type', None)
            if filter_type:
                processed_image = image_filter(image, filter_type)
            else:
                processed_image = image

        elif operation == 'remove_bg':
            bg_color = request.form.get('bg_color', None)
            no_bg_color = 'no_bg_color' in request.form  # Check if "None" option is selected
            api_key = 'sLKdH8N4JtmF6FLwgfgfpmMD'  # Replace with your remove.bg API key
            processed_image = remove_background(image, api_key, bg_color, no_bg_color)

        elif operation == 'enhance':
            enhancement_type = request.form.get('enhancement_type', None)
            factor = float(request.form.get('factor', 1.0))  # Default factor to 1.0 if not provided
            if enhancement_type:
                processed_image = image_enhance(image, enhancement_type, factor)
            else:
                processed_image = image

        filename = file.filename
        saved_filename = save_image(processed_image, filename)
        image_url = url_for('static', filename=f'uploads/{saved_filename}')
        return render_template('index.html', image_url=image_url, filename=saved_filename)

    return render_template('index.html')

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
