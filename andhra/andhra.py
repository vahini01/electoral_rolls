#!/usr/bin/env python3

from io import TextIOWrapper
import re, requests, time, os, pickle, logging
from logging.handlers import RotatingFileHandler
from requests.exceptions import ReadTimeout, ConnectionError, ChunkedEncodingError
from copy import deepcopy
from bs4 import BeautifulSoup
from config import ANDHRA_TRACK_DIR, ANDHRA_PDF_ENGLISH_DIR, ANDHRA_PDF_TELUGU_DIR
from helpers import getpath, timestamp, TRACK_FILE_TS, urlparse, urljoin, append_csv, relpath, randf, tailstr
from selenium import webdriver
import json
from PIL import Image
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from urllib.request import urlopen
import os
import cv2
import pytesseract
from PIL import Image
import urllib.request
import time
# Assignment
ASSIGNED_DISTRICTS = []
ASSIGNED_ID = 0

# Tuning
ENABLE_RESUME = True
TOTAL_RETRIES = 10  # times
REQUEST_TIMEOUT = 20  # seconds
RETRY_DELAY = 5  # seconds
REFRESH_DELAY = 10  # seconds
REFRESH_REQUEST_TIMEOUT = 30  # seconds
REFRESH_TOTAL_RETRIES = 3
DELAY_MIN = 0  # seconds
DELAY_MAX = 0  # seconds
DELAY_FRACTION = 999999

# Connection settings
USER_AGENT = 'Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:57.0) Gecko/20100101 Firefox/57.0'
ANDHRA_URL = 'https://ceoaperolls.ap.gov.in/AP_Eroll/Rolls'
ANDHRA_BASE_URL = 'https://ceoaperolls.ap.gov.in/AP_Eroll'

# /html/body/form/table/tbody/tr[1]/td[2]/img
# /html/body/form/table/tbody/tr[2]/td[2]/input


# Parsing & saving
FIND_PDF_REGEX = re.compile(r"open\('(.+)',")
OUTPUT_FILE = getpath(ANDHRA_TRACK_DIR, 'Andhra{}-{}.csv'.format(ASSIGNED_ID or '', timestamp(TRACK_FILE_TS)))
print(OUTPUT_FILE)
DOWNLOAD_FAILED = 'Not available / Unable to download'
TRACK_FILE = getpath('cache/andhra{}_track.bin'.format(ASSIGNED_ID or ''))

print(TRACK_FILE)
CSV_HEADER = (
    'district_name',
    'ac_name',
    'polling_station_number',
    'polling_station_name',
    'polling_station_location',
    'telugu_file_name',
    'eng_file_name'
)

# Log settings
MAX_LOG_SIZE = 52428800
LOG_BACKUP_COUNT = 5
LOG_FILE = getpath('/Users/vahini/Desktop/btp/electoral_rolls/andhra/logs/andhra{}.log'.format(ASSIGNED_ID or ''))
print(LOG_FILE)

def log_configurer():
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    formatter = logging.Formatter(fmt='%(message)s')

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(formatter)

    fileHandler = RotatingFileHandler(getpath(LOG_FILE), maxBytes=MAX_LOG_SIZE, backupCount=LOG_BACKUP_COUNT)
    fileHandler.setFormatter(formatter)

    root.addHandler(consoleHandler)
    root.addHandler(fileHandler)

    return root


class ExitRequested(Exception):
    pass


class Track:

    def __init__(self):
        self._data = None
        self._done = False
        self.__load()

    def __load(self):
        self.initialize()
        if ENABLE_RESUME:
            if os.path.isfile(TRACK_FILE):
             try:
                with open(TRACK_FILE, 'rb') as file:
                    self._data.update(pickle.load(file))
             except EOFError:
                 self.data = None

    def initialize(self):
        self._data = {
            'done:district': 0,
            'done:ac': 0,
            'done:station': 0,
            'current:step': 0,
            'current:district': 0,
            'current:ac': 0,
            'output': None
        }

    def set_done(self):
        self.initialize()
        self._done = True

    def save(self):
        if self._done:
            if os.path.isfile(TRACK_FILE):
                os.remove(TRACK_FILE)
        else:
            if ENABLE_RESUME:
                with open(TRACK_FILE, 'wb') as file:
                    pickle.dump(self._data, file)

    @property
    def output(self):
        if self._data['output'] is None:
            self._data['output'] = OUTPUT_FILE
        return self._data['output']

    def get_done_dist(self):
        return self._data.get('done:district')

    def set_done_dist(self, value):
        self._data['done:district'] = int(value)
        self._data['done:ac'] = 0
        self._data['done:station'] = 0

    def get_done_ac(self):
        return self._data['done:ac']

    def set_done_ac(self, value):
        self._data['done:ac'] = int(value)
        self._data['done:station'] = 0

    def get_done_station(self):
        return self._data['done:station']

    def set_done_station(self, value):
        self._data['done:station'] = int(value)

    def get_cur_step(self):
        return self._data['current:step']

    def set_cur_step(self, value):
        self._data['current:step'] = int(value)

    def get_cur_dist(self):
        return self._data['current:district']

    def set_cur_dist(self, value):
        self._data['current:district'] = int(value)

    def get_cur_ac(self):
        return self._data['current:ac']

    def set_cur_ac(self, value):
        self._data['current:ac'] = int(value)


class Session:

    def __init__(self):
        self._delay = 0
        self.referer = None
        self.cookies = None
        self.state = None
        self.validation = None
        self.headers = {'user-agent': USER_AGENT}
        self.track = Track()

    def save_track(self):
        self.track.save()

    def __parse(self, response):
        soup = BeautifulSoup(response.text, 'lxml')

        state = soup.find('input', {'id': '__VIEWSTATE'})
        if state is None:
            logger.warning('Error parsing response!')
            raise AssertionError

        validation = soup.find('input', {'id': '__EVENTVALIDATION'})
        if validation is None:
            logger.warning('Error parsing response!')
            raise AssertionError

        self.state = state.get('value')
        self.validation = validation.get('value')

        self.referer = response.request.url
        if self.cookies is None:
            self.cookies = response.cookies

        return soup

    def __error(self):
        fmt = 'Errors occurred with session:\n\t+ Cookie: {}\n\t+ Validation: {}\n\t+ State: {}'
        logger.warning(fmt.format(
            self.cookies.get('ASP.NET_SessionId'), tailstr(self.validation, 50), tailstr(self.state, 50)))
        raise ExitRequested

    def __prep(self):
        headers = deepcopy(self.headers)
        if self.referer:
            headers['referer'] = self.referer
        ret = {'headers': headers}
        if self.cookies:
            ret['cookies'] = self.cookies
        return ret

    def __postdata(self, target, district, ac, get_stations):
        data = {
            '__EVENTTARGET': target,
            '__EVENTARGUMENT': '',
            '__LASTFOCUS': '',
            '__VIEWSTATE': self.state,
            '__EVENTVALIDATION': self.validation,
            'ddlDist': str(district),
            'ddlAC': str(ac),
        }
        if get_stations:
            data['btnGetPollingStations'] = 'Get+Polling+Stations'
        return data

    def __refresh(self):
        self.referer = None
        self.cookies = None
        headers = self.__prep()

        step = self.track.get_cur_step()
        dist_num = self.track.get_cur_dist()
        ac_num = self.track.get_cur_ac()

        logger.warning('Waiting %s seconds for refreshing...' % REFRESH_DELAY)
        time.sleep(REFRESH_DELAY)

        if 0 <= step:
            try:
                logger.warning('Loading Main page...')
                response = requests.get(ANDHRA_URL, timeout=REFRESH_REQUEST_TIMEOUT, **headers)
            except (ReadTimeout, ConnectionError, ChunkedEncodingError):
                logger.warning('Time out or connection error!')
                return False
            else:
                if response.status_code != requests.codes.OK:
                    logger.warning('Could not load Main page: %s %s' % (response.status_code, response.reason))
                    return False
                try:
                    self.__parse(response)
                except AssertionError:
                    return False
                else:
                    logger.warning('Main page loaded successfully.')

        if 1 <= step:
            time.sleep(self.delay)
            headers = self.__prep()
            data = self.__postdata(target='ddlDist', district=str(dist_num), ac='0', get_stations=False)
            try:
                logger.warning('Listing District #%s...' % dist_num)
                response = requests.post(ANDHRA_URL, data=data, timeout=REFRESH_REQUEST_TIMEOUT, **headers)
            except (ReadTimeout, ConnectionError, ChunkedEncodingError):
                logger.warning('Time out or connection error!')
                return False
            else:
                if response.status_code != requests.codes.OK:
                    logger.warning(
                        'Could not list District #%s: %s %s' % (dist_num, response.status_code, response.reason))
                    return False
                try:
                    self.__parse(response)
                except AssertionError:
                    return False
                else:
                    logger.warning('District #%s listed successfully.' % dist_num)

        if 2 <= step:
            time.sleep(self.delay)
            headers = self.__prep()
            data = self.__postdata(target='', district=str(dist_num), ac=str(ac_num), get_stations=True)
            try:
                logger.warning('Listing Stations for AC #%s of District #%s...' % (ac_num, dist_num))
                response = requests.post(ANDHRA_URL, data=data, timeout=REFRESH_REQUEST_TIMEOUT ** headers)
            except (ReadTimeout, ConnectionError, ChunkedEncodingError):
                logger.warning('Time out or connection error!')
                return False
            else:
                if response.status_code != requests.codes.OK:
                    logger.warning('Could not list Stations for AC #%s of District #%s: %s %s' % (
                        ac_num, dist_num, response.status_code, response.reason))
                    return False
                try:
                    self.__parse(response)
                except AssertionError:
                    return False
                else:
                    logger.warning('Stations listed successfully.')

        logger.warning('Successfully refreshed!')
        return True

    def __browse(self, method, url=None, parse=True, **kwargs):
        url = url or ANDHRA_URL
        headers = self.__prep()
        browser = getattr(requests, method)
        tried = 0
        while tried <= TOTAL_RETRIES:
            tried += 1
            time.sleep(self.delay)
            try:
                response = browser(url, timeout=REQUEST_TIMEOUT, **kwargs)
            except (ReadTimeout, ConnectionError, ChunkedEncodingError):
                logger.warning('Timeout or connection error!')
                if tried <= TOTAL_RETRIES:
                    self.__retry()
                    continue
            else:
                if response.status_code == requests.codes.OK:
                    try:
                        return self.__parse(response) if parse else response
                    except AssertionError:
                        break
                else:
                    logger.warning('Error response: %s %s %s' % (
                        response.request.method, response.status_code, response.reason))
        self.__error()

    def __retry(self, seconds=None):
        seconds = seconds or RETRY_DELAY
        logger.warning('Will retry in %s seconds...' % seconds)
        self._delay = seconds

    def __getfile(self, query):
        parsed = urlparse(query).query
        if parsed.startswith('urlPath=') and parsed.lower().endswith('.pdf'):
            return parsed[8:].split('\\')[-1]
        logger.warning('Could not parse file name. Unsupported query string: %s' % query)
        self.__error()

    @property
    def refreshed(self):
        while not self.__refresh():
            continue
        return True

    @property
    def delay(self):
        if self._delay > 0:
            ret = self._delay
            self._delay = 0
            return ret
        return randf(DELAY_MIN, DELAY_MAX, DELAY_FRACTION)

    def get(self):
        count = 0
        while count < REFRESH_TOTAL_RETRIES:
            try:
                return self.__browse(method='get')
            except ExitRequested:
                count += 1
                if count <= REFRESH_TOTAL_RETRIES:
                    if self.refreshed:
                        continue
                    else:
                        break
        self.__error()

    def post(self, target='', district='0', ac='0', get_stations=False):
        count = 0
        while count <= REFRESH_TOTAL_RETRIES:
            data = self.__postdata(target, district, ac, get_stations)
            try:
                return self.__browse(method='post', data=data)
            except ExitRequested:
                count += 1
                if count <= REFRESH_TOTAL_RETRIES:
                    if self.refreshed:
                        continue
                    else:
                        break
        self.__error()

    def fetch(self, query, dest):
        if os.path.isdir(dest):
            file = os.path.join(dest, self.__getfile(query))

            if os.path.isfile(file):
                logger.warning('--> File existed: %s' % file)
                return file

            else:
                url = urljoin(ANDHRA_BASE_URL, query)
                logger.warning('--> Downloading %s...' % url)

                count = 0
                while count <= REFRESH_TOTAL_RETRIES:
                    try:
                        response = self.__browse(method='get', url=url, parse=False)
                    except ExitRequested:
                        count += 1
                        if count > REFRESH_TOTAL_RETRIES:
                            return None
                        if self.refreshed:
                            continue
                        else:
                            break
                    else:
                        with open(file, 'wb') as f:
                            f.write(response.content)
                        return file
        else:
            logger.warning('Destination folder was not found: %s' % dest)
        self.__error()


class Andhra:

    def __init__(self, session):
        self.session = session
        self.soup = None
        self.districts = []

    def download(self):
        if not os.path.isfile(self.session.track.output):
            append_csv(self.session.track.output, CSV_HEADER)


        logger.warning('Finding Districts...')
        self.session.track.set_cur_step(0)
        self.soup = self.session.get()

        select = self.soup.find('select', {'id': 'ddlDist'})
        if select is None:
            logger.warning('Could not parse Districts in response!')
            raise ExitRequested

        options = select.find_all('option')
        if len(options) < 2:
            logger.warning('No District found!')
            raise ExitRequested

        logger.warning('Found %s Districts.' % (len(options) - 1))
        done_dist = self.session.track.get_done_dist()
        #done_dist = 2



        for option in options[1:]:
            dist_num = option.get('value')
            dist_name = option.text.strip()

            if ASSIGNED_DISTRICTS and int(dist_num) not in ASSIGNED_DISTRICTS:
                logger.warning('Skipped District "%s" (Not Assigned)' % dist_name)
                continue
            if int(dist_num) <= done_dist:
                logger.warning('Skipped District "%s" (Done Already)' % dist_name)
                continue
            District(num=dist_num, name=dist_name, session=self.session)

        logger.warning('Completed successfully.')
        self.session.track.set_done()


class District:

    def __init__(self, num, name, session):
        self.num = num
        self.name = name
        self.session = session
        self.soup = None
        self.acs = []
        self.download()

    def download(self):
        logger.warning('Finding ACs of District "%s"...' % self.name)
        self.session.track.set_cur_step(1)
        self.session.track.set_cur_dist(self.num)
        self.soup = self.session.post(target='ddlDist', district=self.num)

        select = self.soup.find('select', {'id': 'ddlAC'})
        if select is None:
            logger.warning('Could not parse ACs in response!')
            raise ExitRequested

        options = select.find_all('option')
        if len(options) < 2:
            logger.warning('No AC found for District "%s"!' % self.name)
            raise ExitRequested

        logger.warning('Found %s ACs for District "%s".' % (len(options) - 1, self.name))
        done_ac = self.session.track.get_done_ac()
        #done_ac = 12

        for option in options[1:]:
            ac_num = option.get('value')
            ac_name = option.text.strip()

            if int(ac_num) <= done_ac:
                logger.warning('Skipped AC "%s" of District "%s"' % (ac_name, self.name))
                continue

            AC(
                num=ac_num,
                name=ac_name,
                dist_num=self.num,
                dist_name=self.name,
                session=self.session
            )

        self.session.track.set_done_dist(self.num)


class AC:

    def __init__(self, num, name, dist_num, dist_name, session):
        self.num = num
        self.name = name
        self.dist_num = dist_num
        self.dist_name = dist_name
        self.session = session
        self.soup = None
        self.stations = []
        self.download()

    def download(self):
        logger.warning('Finding Stations of AC "%s" of District "%s"...' % (self.name, self.dist_name))
        self.session.track.set_cur_step(2)
        self.session.track.set_cur_dist(self.dist_num)
        self.session.track.set_cur_ac(self.num)
        self.soup = self.session.post(district=self.dist_num, ac=self.num, get_stations=True)

        table = self.soup.find('table', {'id': 'GridView1'})
        if table is None:
            logger.warning('Could not parse Stations in response!')
            raise ExitRequested

        tr = table.find_all('tr')

        if len(tr) < 2:
            logger.warning('No Stations found for AC "%s" of District "%s"!' % (self.name, self.dist_name))
            raise ExitRequested

        logger.warning('Found %s Stations for AC "%s" of District "%s".' % (len(tr) - 1, self.name, self.dist_name))

        done_station = self.session.track.get_done_station()
        #done_station=13

        for row in tr[1:]:

            td = row.find_all('td')

            if len(td) != 5:
                logger.warning('Unexpected row: %s' % row)
                continue
            num = td[0].text.strip()
            name = td[1].text
            loc = td[2].text
            telugu = td[3].find('a').get('id').replace('_', '$')
            english = td[4].find('a').get('id').replace('_', '$')

            if int(num) <= done_station:
                logger.warning(
                    'Skipped Station "%s-%s" of AC "%s" of District "%s"' % (num, name, self.name, self.dist_name))
                continue

            Station(num, name, loc, telugu, english, self.num, self.name, self.dist_num, self.dist_name, self.session)

        self.session.track.set_done_ac(self.num)


class Station:

    def __init__(self, num, name, loc, telugu, english, ac_num, ac_name, dist_num, dist_name, session):
        self.num = num
        self.name = name
        self.location = loc
        self.telugu = telugu
        self.english = english
        self.ac_num = ac_num
        self.ac_name = ac_name
        self.dist_num = dist_num
        self.dist_name = dist_name
        self.session = session
        self.telugu_dir = getpath(ANDHRA_PDF_TELUGU_DIR)
        self.english_dir = getpath(ANDHRA_PDF_ENGLISH_DIR)
        self.telugu_soup = None
        self.english_soup = None
        self.telugu_file = None
        self.english_file = None
        self.download()

    def expand_shadow_element(self,driver,element):
        shadow_root = driver.execute_script('return arguments[0].shadowRoot', element)
        return shadow_root

    def __bypass_captcha(self,url, language):


     while(1):
        chrome_options = webdriver.ChromeOptions()
        settings = {
            "recentDestinations": [{
                "id": "Save as PDF",
                "origin": "local",
                "account": "",
            }],
            "selectedDestinationId": "Save as PDF",
            "version": 2
        }
        prefs = {'printing.print_preview_sticky_settings.appState': json.dumps(settings)}
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_argument('--kiosk-printing')
        # chrome_options.add_argument('headless');

        driver = webdriver.Chrome(options = chrome_options, executable_path="/usr/local/bin/chromedriver")
        driver.get(url)
        image = driver.find_element_by_id('form1').screenshot("/Users/vahini/Desktop/btp/electoral_rolls/andhra/aa.png")

        image = cv2.imread('/Users/vahini/Desktop/btp/electoral_rolls/andhra/aa.png')
        image = cv2.resize(image, (0, 0), fx=1.2, fy=2)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        filename = "{}.png".format("temp")
        cv2.imwrite(filename, gray)
        text = pytesseract.image_to_string(Image.open('temp.png'))
        #print(text)

        captchaEntry = driver.find_element_by_id('txtVerificationCode')
        captchaEntry.send_keys(text[18:24])
        wait = WebDriverWait(driver, 10)
        element = wait.until(EC.element_to_be_clickable((By.ID, 'btnSubmit')))
        element.click()
        # submitButton = driver.find_element_by_id('btnSubmit')
        #
        #
        # submitButton.click()



        delay = 10  # seconds
        try:
            captchamsg = driver.find_element_by_id('lblCaptchaMessage');
            if(captchamsg):
                print('Captcha entered is incorrect')
                #self.__bypass_captcha(url)
        except NoSuchElementException:
                print("Captcha Passed")
                try:
                    secs= 20
                    time.sleep(secs)
                    driver.implicitly_wait(secs)


                    driver.execute_script('window.print();')

                    time.sleep(secs)



                    old_file_name = "/Users/vahini/Downloads/Popuppage.pdf"
                    new_file_name = "/Users/vahini/Downloads/" + language.capitalize() + "_distno_" + self.dist_num + "_acno_" + self.ac_num + "_partno_" + self.num+".pdf"
                    if(os.path.isfile(old_file_name)):
                        os.rename(old_file_name, new_file_name)
                        driver.implicitly_wait(secs)
                        break;
                    else:
                        print("Loading took too much time!")


                except TimeoutException:
                     print("Loading took too much time!")
        driver.quit()

    def __fetch_pdf(self, lang):
        target = getattr(self, lang)
        dir_ = getattr(self, '%s_dir' % lang)
        # print(self.dist_name)
        # print(self.ac_num)
        # print(self.ac_name)
        # print(self.num)

        temp = self.ac_num


        URL = ANDHRA_BASE_URL + '/Popuppage?'
        partnumber = 'partNumber='+self.num
        roll = 'roll=' + lang.capitalize() + 'MotherRoll'
        districtname = 'districtName=DIST_'+  str(self.dist_num).zfill(2)
        acname ='acname='+ temp
        acnameeng = 'acnameeng=A'+ temp
        acno = 'acno='+ temp
        acnameurdu = 'acnameurdu=' + str(temp).zfill(3)

        finalurl = URL + partnumber + '&' + roll + '&' +districtname + '&' + acname + '&' + acnameeng + '&' + acno + '&' + acnameurdu

        print(finalurl)
        self.__bypass_captcha(finalurl,lang)

        logger.warning('Downloading %s PDF...' % lang.capitalize())


        soup = self.session.post(target=target, district=self.dist_num, ac=self.ac_num)

        script = soup.find('script')


        if script is None:
            logger.warning('Could not parse %s download link in response!' % lang.capitalize())
            raise ExitRequested

        try:
            link = FIND_PDF_REGEX.findall(script.text)[0]
            #link ='https://ceoaperolls.ap.gov.in/AP_Eroll/Popuppage?partNumber=1&roll=EnglishMotherRoll&districtName=DIST_02&acname=11&acnameeng=A11&acno=11&acnameurdu=011'

        except IndexError:
            logger.warning('No %s download link responded!' % lang.capitalize())
            file = None
            setattr(self, '%s_soup' % lang, soup)
            setattr(self, '%s_file' % lang, file)

        else:
            file = self.session.fetch(query=link, dest=dir_)
            setattr(self, '%s_soup' % lang, soup)
            setattr(self, '%s_file' % lang, file)

    def download(self):
        logger.warning('Processing: Station "%s-%s", AC "%s", District "%s"...' % (
            self.num, self.name, self.ac_name, self.dist_name))
        self.__fetch_pdf('telugu')
        self.__fetch_pdf('english')
        row = (
            self.dist_name,
            self.ac_name,
            self.num,
            self.name,
            self.location,
            relpath(self.telugu_file) if self.telugu_file is not None else DOWNLOAD_FAILED,
            relpath(self.english_file) if self.english_file is not None else DOWNLOAD_FAILED
        )
        append_csv(self.session.track.output, row)

        self.session.track.set_done_station(self.num)
        done_station = self.session.track.get_done_station()

        self.session.save_track()



def main():
    session = Session()
    site = Andhra(session)
    try:
        site.download()
    except (KeyboardInterrupt, ExitRequested):
        session.save_track()
        print("Keyboard interrupt")
        pass
    finally:
        session.save_track()
        logger.warning('Exited!')


if __name__ == '__main__':
    logger = log_configurer()
    main()
