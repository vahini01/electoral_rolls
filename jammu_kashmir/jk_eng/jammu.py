#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 14 09:04:53 2017

@author: dhingratul
"""

import os
import selenium
from selenium import webdriver
from selenium.webdriver.support.ui import Select
import sys
from selenium.webdriver.common.keys import Keys
import pytesseract
from pytesseract import image_to_string
from PIL import Image
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import io


def getDistrict(driver, element):
    mySelect_D = Select(driver.find_element_by_id(element))
    num_D = len(mySelect_D.options)  # Start from 1, 0 -- Select
    return driver, mySelect_D, num_D


def refresh(m_url, i, j, k, flag="C"):
    options = webdriver.ChromeOptions()
    prefs = {'download.default_directory': mdir}
    options.add_experimental_option('prefs', prefs)
    driver = webdriver.Chrome(options=options)
    driver.get(m_url)
    driver.find_element_by_css_selector("input[type='radio'][value='PS Wise Report']").click()
    driver.find_element_by_css_selector("input[type='radio'][value='English']").click()
    button = driver.find_element_by_xpath('//*[@id="Button1"]')
    button.send_keys(Keys.ENTER)
    driver, mySelect_D, num_D = getDistrict(driver, "DistlistP")
    mySelect_D.options[i].click()
    driver, mySelect_C, num_C = getDistrict(driver, "AclistP")
    if flag == "C":
        mySelect_C.options[j].click()
    driver, mySelect_P, num_P = getDistrict(driver, "PslistP")
    return driver, mySelect_P, mySelect_C, mySelect_D


def checkComplete(ctr):
    L = os.listdir(mdir)
    res = [x.split(".") for x in L]
    res2 = [x[-1] == 'pdf' for x in res]
    ctr2 = sum(res2)
    if ctr2 == ctr + 1:
        return True
    else:
        return False

def get_captcha_text(location, size):
    # pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files (x86)/Tesseract-OCR/tesseract'
    # im = Image.open('screenshot.png') # uses PIL library to open image in memory
    #
    # left = location['x']
    # top = location['y']
    # right = location['x'] + size['width']
    # bottom = location['y'] + size['height']
    #
    #
    # im = im.crop((left, top, right, bottom)) # defines crop points
    # im.save('screenshot.png')
    print(f"#{captcha_text}#")
    return captcha_text

def bypass_captcha(driver):
    #find part of the page you want image of
    element = driver.find_element_by_xpath('//*[@id="Panel1"]/center/div/img')
    location = element.location
    size = element.size
    driver.save_screenshot('screenshot.png')
    im = Image.open('screenshot.png') # uses PIL library to open image in memory
    #
    left = location['x']
    top = location['y']
    right = location['x'] + size['width']
    bottom = location['y'] + size['height']


    im = im.crop((left, top, right, bottom)) # defines crop points
    im.save('screenshot.png')
    # image = element.screenshot_as_png
    # imageStream = io.BytesIO(image)
    # im = image.open(imageStream)
    element.screenshot('test.png')
    captcha_text = pytesseract.image_to_string(Image.open('test.png'))
        import pdb; pdb.set_trace()
    captcha_text = "text"
    return captcha_text


mdir = '../data/JK/'
L = os.listdir(mdir)
res = [x.split(".") for x in L]
res2 = [x[-1] == 'pdf' for x in res]
ctr2 = sum(res2)
ctr = ctr2
m_url = 'http://ceojk.nic.in/ElectionPDF/Main.aspx'
options = webdriver.ChromeOptions()
prefs = {'download.default_directory':  mdir}
options.add_experimental_option('prefs', prefs)
driver = webdriver.Chrome(options=options)
driver.get(m_url)
driver.find_element_by_css_selector("input[type='radio'][value='PS Wise Report']").click()
driver.find_element_by_css_selector("input[type='radio'][value='English']").click()
button = driver.find_element_by_xpath('//*[@id="Button1"]')
button.send_keys(Keys.ENTER)
driver, mySelect_D, num_D = getDistrict(driver, "DistlistP")
i_start = 1
j_start = 1
k_start = 1
for i in range(i_start, num_D):
    if i != i_start:
        driver, mySelect_P, mySelect_C, mySelect_D = refresh(m_url, i, 0, 0, flag="D")
    else:
        mySelect_D.options[i].click()
    driver, mySelect_C, num_C = getDistrict(driver, "AclistP")
    for j in range(j_start, num_C):
        if j != 1:
            driver, mySelect_P, mySelect_C, mySelect_D = refresh(m_url, i, j, k)
        else:
            mySelect_C.options[j].click()
        driver, mySelect_P, num_P = getDistrict(driver, "PslistP")
        for k in range(k_start, num_P):
            print('\n', i, j, k,)
            mySelect_P.options[k].click()
            # Bypass captcha
            driver.set_window_position(0, 0)
            driver.set_window_size(1024, 768)
            text = bypass_captcha(driver)
            print(text)
            # Enter captcha

            # # Click button
            wait = WebDriverWait(driver, 10)
            element = wait.until(EC.element_to_be_clickable((By.ID, 'BtnPs')))
            # driver.find_element_by_css_selector('#BtnPs').click()
            try:
                button = driver.find_element_by_xpath('//*[@id="LnkFile"]')
                button.send_keys(Keys.ENTER)
            except selenium.common.exceptions.NoSuchElementException:
                with open("jammu.txt", "a") as myfile:
                    myfile.write(str(i) + ',' + str(j) + ',' + str(k) + '\n')
                    driver.quit()
                    driver, mySelect_P, _, _ = refresh(m_url, i, j, k, flag="C")
                    flag = True
                    # continue
            flag = False
            while flag is False:
                flag = checkComplete(ctr)
            ctr += 1
            driver.quit()
            if k != num_P - 1:
                driver, mySelect_P, _, _ = refresh(m_url, i, j, k, flag="C")
            break
        break
    break

    driver.quit()
    # driver, _, _, mySelect_D = refresh(m_url, i, j, k)
