## Scraping for Letterboxd using BeautifulSoup and requests

# imports used
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json


def scrap_letterboxd(username: str):
    page_number = 1
    movie_names = []
    movie_slugs = []
    movie_ratings = []
    movie_images = []
    while True:
        # Given the username, create the letterboxd url so we can scrap the movies
        url = "https://letterboxd.com/" + username.strip() + "/films/page/" + str(page_number) + "/"
        response = requests.get(url)

        # Initialize the regular expressions which will scan the soup file
        # for all of the movie names and star ratings.
        regex_movie_names = re.compile(r'alt="([^"]+)"')
        regex_movie_slugs = re.compile(r'data-film-slug="([^"]+)"')
        regex_movie_ratings = re.compile(r"rated-(\d+)")

        # Make the soup to pull everything off the users letterboxd webpage.
        soup = BeautifulSoup(requests.get(url).text, "html.parser")

        # Now find everything from only the actual movie section of the webpage, not the other info
        film_html = soup.find_all("li", class_=re.compile(r"poster-container"))

        # If there aren't any films found, break out of the loop
        if not film_html:
            break

        # Now, using regex, we get all the movie names and ratings from the HTML file.
        # This automatically creates a list for each variable.
        movie_names = re.findall(regex_movie_names, str(film_html))
        movie_slugs = re.findall(regex_movie_slugs, str(film_html))
        movie_ratings = re.findall(regex_movie_ratings, str(film_html))

        page_number += 1

    """ Now we're going to remove the movies from the users letterbox'd that don't
        have a rating associated with them. Because it won't add to the model and
        it will break when we try and create a dataframe.   """
    # We now get the url for the movies that don't have any reviews.
    url_no_reviews = "https://letterboxd.com/" + username.strip() + "/films/rated/none/"

    # Make the soup to pull everything off that webpage.
    soup = BeautifulSoup(requests.get(url_no_reviews).text, "html.parser")

    # Now scrap everything from only the reviews section. that is the 'list__...'
    film_html_no_reviews = soup.find_all("li", class_=re.compile(r"poster-container"))

    # Get the list of all the removed movies.
    removed_movie_names = re.findall(r'alt="([^"]+)"', str(film_html_no_reviews))
    removed_movie_slugs = re.findall(r'data-film-slug="([^"]+)"', str(film_html_no_reviews))

    """ Loop over all the movies we found, and remove them so that
    len(movie_names) == len(movie_ratings) and we don't have movies without ratings
    If the movie exists within the lists we should remove it
    We wont need this when we scrape all the movies instead of
    only the first page. """
    movie_names = [movie for movie in movie_names if movie not in removed_movie_names]
    movie_slugs = [movie for movie in movie_slugs if movie not in removed_movie_slugs]
    movie_ratings = [int(rating) for rating in movie_ratings]

    # Get the images for the movies
    # Lowkey stole this code from https://stackoverflow.com/questions/73803684/trying-to-scrape-posters-from-letterboxd-python
    movie_images = []
    for movie in movie_slugs:
        url = f"https://letterboxd.com/film/{movie}/"
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")

        script_w_data = soup.select_one('script[type="application/ld+json"]')
        json_obj = json.loads(script_w_data.text.split(" */")[1].split("/* ]]>")[0])
        movie_images.append(json_obj["image"])

    # Return the results
    return movie_names, movie_slugs, movie_ratings, movie_images

def scrape_letterboxd_movie(movie_slug: str):
    """
    Scrapes details of a specific movie from Letterboxd using its slug.
    
    Args:
    - movie_slug: The slug part of the movie URL on Letterboxd (e.g., 'joker-folie-a-deux' for 'letterboxd.com/film/joker-folie-a-deux/')
    
    Returns:
    - Dictionary containing movie title, release year, genres, director, rating, and poster image URL.
    """
    movie_slug = movie_slug.strip()  # Clean the movie_slug of any leading/trailing whitespace
    url = f"https://letterboxd.com/film/{movie_slug}/"
    response = requests.get(url)
    
    if response.status_code != 200:
        raise Exception(f"Failed to retrieve data. Status code: {response.status_code}")
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    print("Soup successfully parsed.")
    
    # Extract JSON-LD data which contains movie details
    script_data = soup.select_one('script[type="application/ld+json"]')
    if not script_data:
        print("Movie data not found on the page.")
        raise ValueError("Movie data not found on the page.")

    # Get the content of the script and strip the CDATA tags
    raw_data = script_data.string
    if raw_data.startswith('/* <![CDATA[ */'):
        raw_data = raw_data.replace('/* <![CDATA[ */', '').replace('/* ]]> */', '').strip()

    try:
        movie_data = json.loads(raw_data)
        print("Movie data successfully parsed.")
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", str(e))
        print("Invalid JSON data:", raw_data)
        
        # Return fake movie data if JSON decoding fails
        return {
            "title": "Unknown Movie",
            "year": "N/A",
            "genres": ["Drama"],
            "director": "N/A",
            "rating": 0.0,
            "poster_url": "https://via.placeholder.com/150"
        }

    # Extract details from the JSON data
    title = movie_data.get("name", "Unknown Movie")
    year = movie_data.get("datePublished", "").split("-")[0] or "N/A"
    genres = movie_data.get("genre", [])
    director = movie_data.get("director", [{}])[0].get("name", "N/A")
    rating = movie_data.get("aggregateRating", {}).get("ratingValue", 0.0)
    poster_url = movie_data.get("image", "https://via.placeholder.com/150")

    return {
        "title": title,
        "year": year,
        "genres": genres,
        "director": director,
        "rating": rating,
        "poster_url": poster_url,
    }


# Method to scrape a given letterboxd username and return a dataframe with the movie names and the star ratings.
def scrape_and_make_dataframe(username: str) -> pd.DataFrame:
    # Scrap the movies and ratings from the given letterboxd username
    (movie_name, movie_slugs, movie_rating, movie_images) = scrap_letterboxd(username)

    # Convert the ratings from string to integer using list comprehension
    int_movie_ratings = [int(i) for i in movie_rating]

    # Make a list of size (movie_name) for the usernames, Not necessary just included it
    username_list = [username] * len(movie_name)

    # Return the results as a Pandas dataframe
    return pd.DataFrame(
        {
            "user_name": username_list,
            "film_id": movie_slugs,
            "Movie_name": movie_name,
            "rating": int_movie_ratings,
            "image": movie_images,
        }
    )


if __name__ == "__main__":
    # Sample use
    username = input("Please type your letterboxd username : ")
    print(f"Now scraping : {username}")
    df = scrape_and_make_dataframe(username.strip())
    print(df)
