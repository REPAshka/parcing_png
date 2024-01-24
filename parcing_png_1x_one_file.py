import pandas as pd
import re
import time
import gspread as gs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import List
from bs4 import BeautifulSoup

import warnings
warnings.simplefilter('ignore')

from loguru import logger

log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
logger.add("output.log", level="INFO", format=log_format, rotation="10 KB", compression="zip")


def get_top_games_img_urls(url: str, need_to_change_iframes: bool=False, need_to_cancel_second_popup: bool=False) -> List[str]:
    img_urls_search = []

    driver = webdriver.Firefox()
    driver.get(url)
    time.sleep(2)

    # return BeautifulSoup(driver.page_source, 'html.parser')
    if need_to_change_iframes:
        # переходим на айфрейм казино внутри сайта
        iframe_locator = (By.CLASS_NAME, 'body--has-modal body--blurred') #third-party-frame__content
        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it(iframe_locator))
        logger.info('Я НАШЕЛ ТЕЛО ОСНОВОГО АЙФРЕЙМА КАЗИНО')
        time.sleep(5)

        # ищем и закрываем первый попап
        popup_locator = (By.CLASS_NAME, 'body--has-modal body--blurred')
        WebDriverWait(driver, 10).until(EC.presence_of_element_located(popup_locator))
        logger.info('Я НАШЕЛ ТЕЛО АЙФРЕЙМА ПЕРВОГО ПОПАПА')

    time.sleep(12)
    # Xpath к <button class=""> нужно менять на разные попапы / в разные дни
    cancel_button = driver.find_element(By.XPATH, '/html/body/div[3]/div/div/div/div/button')
    cancel_button.click()
    logger.info('Я НАШЕЛ И ЗАКРЫЛ ПЕРВЫЙ ПОПАП')

    if need_to_cancel_second_popup:
        time.sleep(12)
        if need_to_change_iframes:
            # ищем и закрываем второй попап
            popup_locator = (By.CLASS_NAME, 'welcome-bonus-modal__close')
            WebDriverWait(driver, 10).until(EC.presence_of_element_located(popup_locator))

        time.sleep(5)
        # Xpath к <button class=""> нужно менять на разные попапы / в разные дни
        cancel_button = driver.find_element(By.XPATH, '/html/body/div[3]/div/div/div/div/button')
        cancel_button.click()
        logger.info('Я НАШЕЛ И ЗАКРЫЛ ВТОРОЙ ПОПАП')

    if need_to_change_iframes:
        driver.switch_to.default_content()
        # переходим снова на айфрейм казино внутри сайта
        iframe_locator = (By.CLASS_NAME, 'third-party-frame__content')
        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it(iframe_locator))
        time.sleep(2)
    page_content = driver.page_source
    soup = BeautifulSoup(page_content, 'html.parser')

    # return soup
    for c in soup.find_all(class_='casino-game-slot__content'):
        pattern = r'"([^"]*)"'
        for x in re.findall(pattern, c['style']):
            img_urls_search.append(x)
    driver.quit()
    return img_urls_search


def get_img_urls(search_list: List[str], need_to_change_iframes: bool=False, need_to_cancel_second_popup: bool=True) -> List[str]:

    url = 'https://1x001.com/ru/slots'
    img_urls = {}
    img_urls_tops = get_top_games_img_urls(url=url, need_to_change_iframes=need_to_change_iframes, need_to_cancel_second_popup=need_to_cancel_second_popup)
    # return img_urls_tops
    logger.info(len(img_urls_tops))


    driver = webdriver.Firefox()
    driver.get(url)
    time.sleep(2)

    if need_to_change_iframes:
        iframe_locator = (By.CLASS_NAME, 'third-party-frame__content')
        WebDriverWait(driver, 10).until(EC.frame_to_be_available_and_switch_to_it(iframe_locator))
        time.sleep(2)

    search_bar = driver.find_element(by=By.CLASS_NAME, value='casino-main-filter-search__field')
    for search in search_list:
        search_bar.clear()
        search_bar.send_keys(search)
        search_bar.send_keys(Keys.RETURN)  # Submit the search form
        time.sleep(3)

        page_content = driver.page_source
        soup = BeautifulSoup(page_content, 'html.parser')
        img_urls_search = []

        for c in soup.find_all(class_='casino-game-slot__content'):
            pattern = r'"([^"]*)"'
            try:
                for x in re.findall(pattern, c['style']):
                    if x not in img_urls_tops:
                        img_urls_search.append(x)
            except KeyError as k:
                logger.info(f'У игры {search} не нашолся параметр style в коде страницы!')
        img_urls[search] = img_urls_search

    driver.quit()

    return img_urls#, img_urls_tops


def get_final_df(worksheet: gs.worksheet, save_fig_locally: bool=False) -> pd.DataFrame:

    df_spreadsheet = pd.DataFrame(worksheet.get_all_records())

    games_name = df_spreadsheet.query('game_name != ""').game_name.map(lambda x: x.strip()).unique().tolist()
    tt = get_img_urls(games_name, need_to_change_iframes=False, need_to_cancel_second_popup=False)
    df_imgs = pd.DataFrame.from_dict(tt, orient='index')
    logger.info('ВСЕ КАРТИНКИ УСПЕШНО ВЫГРУЖЕНЫ!')


    if save_fig_locally:
        # если нужно сохранить картинки локально
        import requests

        def save_image_from_url(image_url, local_filename):
            response = requests.get(image_url)
            with open(local_filename, 'wb') as file:
                file.write(response.content)

        for row in df_imgs.itertuples():
            for col in df_imgs.columns:
                if col and (row[col] is not None):
                    save_image_from_url(row[col], 'saveg_1x_images/' + row.Index.upper() + ' - ' + row[col].split('/')[-1])


    df_to_spreadsheet = df_imgs.reset_index().rename(columns={'index': 'game_name'})
    # дропаeм колонки, если там везде везде одно значение
    for col in df_to_spreadsheet.columns:
        if (df_to_spreadsheet[col].isna().sum() == 0) and (df_to_spreadsheet[col].nunique() == 1):
            df_to_spreadsheet = df_to_spreadsheet.drop(columns=[col])
    logger.info('Таблица к записи в спредшит файл готова!')

    return df_to_spreadsheet



if __name__ == "__main__":
    try:
        gc = gs.service_account(filename='../service_account.json')
        sh = gc.open_by_url('https://docs.google.com/spreadsheets/d/1OlLCCk2KT7pdvEHi5zoDBL8I5_DPXR8q9M5SZtoO-no/edit#gid=348316738')
        worksheet = sh.worksheet('games_to_parce')

        df_to_spreadsheet = get_final_df(worksheet=worksheet, save_fig_locally=False)

        worksheet.update([df_to_spreadsheet.columns.values.tolist()] + df_to_spreadsheet.fillna('').values.tolist())
        print('Спредшит файл успешно записан!')
    except Exception as e:
        logger.exception("HUSTON, WE HAVE AN ERROR: {e}")
#%%
