import today
import shutil

# Make copies of the templates as expected by the script
shutil.copy("templates/dark_mode.svg", "dark_mode.svg")
shutil.copy("templates/light_mode.svg", "light_mode.svg")

values = {
    "age_data": "22 years, 7 months, 18 days",
    "repo_data": "12",
    "contrib_data": "133",
    "star_data": "342",
    "follower_data": "196",
    "commit_data": "2,116",
    "loc_add": "523,178",
    "loc_del": "76,902",
    "loc_net": "446,276",
}

today.svg_overwrite("dark_mode.svg", values)
today.svg_overwrite("light_mode.svg", values)
print("Test completed successfully.")
