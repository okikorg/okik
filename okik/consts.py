from enum import Enum

class ProjectDir(Enum):
    """
    List of all the directories to be created in the project.
    """
    SERVICES_DIR:str = ".okik/services"
    CACHE_DIR:str = ".okik/cache"
    CONFIG_DIR: str = ".okik/configs"
    TEMP_DIR: str = ".okik/temp"
    DOCKER_DIR: str = ".okik/docker"
