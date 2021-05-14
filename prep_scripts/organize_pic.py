import os, shutil

BASE_IMG_DIR = "../data/game_dset/images/results"

def iterate_dir(root_dir):
    for subdir, dirs, files in os.walk(root_dir):
        for file in files:
            src = os.path.join(subdir, file)
            new_filename = "{}_{}".format(os.path.basename(os.path.normpath(subdir)).strip(), file)
            dst = os.path.join(root_dir, new_filename)
            # copies if not exists
            if not os.path.exists(dst):
                shutil.copyfile(src, dst)
            # print(dst)

if __name__=='__main__':
    iterate_dir(BASE_IMG_DIR)