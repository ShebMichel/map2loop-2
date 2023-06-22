
# Installing map2loop

Marks instructions 


1)	create a clean python env with

conda create --name loop python=3.8                 # --name  =  minus minus name (no spaces)! If you already have an env called loop, call it loop2 or something.

2)	download clean code from github (so delete any existing code if you have any)

git clone -b may2021 https://github.com/Loop3D/map2loop-2

git clone -b probability https://github.com/Loop3D/LoopStructural

git clone https://github.com/Loop3D/map2loop2-notebooks

git clone https://github.com/Loop3D/LoopProjectFile

3) conda activate loop

4) conda install git -y

5) conda install cython -y 

6) cd map2loop-2

7) python setup.py develop

8) cd ../LoopStructural

9) pip install -e .

10) cd ../LoopProjectFile

11) python setup.py install

12) pip install lavavu



##################################################


need to install MVSC build tools (https://visualstudio.microsoft.com/downloads/)
conda create --name loop python=3.7 anaconda

conda activate loop


cd map2loop-2
python setup.py develop

conda install git -y
conda install cython -y
conda install six -y



cd ../LoopStructural
pip install -e .
cd ../LoopProjectFile
python setup.py install
pip install lavavu==1.7.6
pip install jupyter
pip install meshio

conda install -c conda-forge folium ipyleaflet ipywidgets -y 
jupyter nbextension enable --py --sys-prefix ipyleaflet



