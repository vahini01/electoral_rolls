from selenium import webdriver
from PIL import Image

import cv2
import pytesseract
from PIL import Image
import urllib.request



driver = webdriver.Chrome("/Users/jalend15/opt/miniconda3/lib/python3.8/site-packages/selenium/webdriver/chrome/chromedriver")

driver.get('https://ceoaperolls.ap.gov.in/AP_Eroll/Popuppage?partNumber=1&roll=EnglishMotherRoll&districtName=DIST_03&acname=22&acnameeng=A22&acno=22&acnameurdu=022')

screenshot = driver.save_screenshot('my_screenshot.png')

image= driver.find_element_by_id('form1').screenshot("/Users/jalend15/Desktop/aa.png")

URL ='https://ceoaperolls.ap.gov.in/AP_Eroll/Popuppage?partNumber=1&roll=EnglishMotherRoll&districtName=DIST_03&acname=22&acnameeng=A22&acno=22&acnameurdu=022'


image = cv2.imread('/Users/jalend15/Desktop/aa.png')
image = cv2.resize(image, (0, 0), fx=1.2, fy=2)
cv2.imwrite("/Users/jalend15/PycharmProjects/electoral_rolls/andhra/cc.png", image)


gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
cv2.imwrite("/Users/jalend15/PycharmProjects/electoral_rolls/andhra/cc.png", gray)

gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY|cv2.THRESH_OTSU)[1]



cv2.imwrite("/Users/jalend15/PycharmProjects/electoral_rolls/andhra/dd.png", gray)


filename = "{}.png".format("temp")
cv2.imwrite(filename, gray)
text = pytesseract.image_to_string(Image.open('temp.png'))
print(text)

captchaEntry = driver.find_element_by_id('txtVerificationCode')
submitButton = driver.find_element_by_id('btnSubmit')



captchaEntry.send_keys(text[18:24])
submitButton.click();




response = urllib.request.urlopen(URL)
file = open("/Users/jalend15/Downloads/FILENAME.pdf", 'wb')
file.write(response.read())
file.close()

driver.quit()