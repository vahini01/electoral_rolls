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

def get_captcha_text(driver):
    #find part of the page you want image of
    element = driver.find_element_by_xpath('//*[@id="Panel1"]/center/div/img')
    element.screenshot('test.png')
    captcha_text = pytesseract.image_to_string(Image.open('test.png'))
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
            # while(1) :
                # driver, mySelect_D, num_D = getDistrict(driver, "DistlistP")
                # if i != i_start:
                #     driver, mySelect_P, mySelect_C, mySelect_D = refresh(m_url, i, 0, 0, flag="D")
                # else:
                #     mySelect_D.options[i].click()
                # driver, mySelect_C, num_C = getDistrict(driver, "AclistP")
                # if j != 1:
                #     driver, mySelect_P, mySelect_C, mySelect_D = refresh(m_url, i, j, k)
                # else:
                #     mySelect_C.options[j].click()
                # driver, mySelect_P, num_P = getDistrict(driver, "PslistP")
                #
                # mySelect_D.options[i].click()
                # mySelect_C.options[j].click()
                # mySelect_P.options[k].click()
            text = get_captcha_text(driver)
            print(text)
            # Enter captcha
            captchaEntry = driver.find_element_by_id('txtinput')
            captchaEntry.send_keys(text)
            # # Click button
            wait = WebDriverWait(driver, 10)
            element = wait.until(EC.element_to_be_clickable((By.ID, 'BtnPs')))
            element.click()
            # check whether captcha is correct or not
            delay = 10  # seconds
            try:
                captchamsg = driver.find_element_by_id('invalidcaptcha');
                if(captchamsg):
                    print('Captcha entered is incorrect')
                    # k = k -1
                    # continue
                    #self.__bypass_captcha(url)
            except NoSuchElementException:
                    print("Captcha Passed")
                    break

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
