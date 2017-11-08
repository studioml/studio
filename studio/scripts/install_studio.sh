repo_url="{repo_url}"
branch="{studioml_branch}"

if [ ! -d "studio" ]; then
    echo "Installing system packages..."
    #sudo add-apt-repository -y ppa:jonathonf/python-3.6
    sudo apt -y update
    sudo apt install -y wget git jq 
    #sudo apt install -y python python-pip python-dev python3.6 python3.6-dev python3-pip
    sudo apt install -y python python-pip python-dev python3 python3-dev python3-pip
    echo "python2 version: " $(python -V)

    sudo python -m pip install --upgrade pip
    sudo python -m pip install --upgrade awscli boto3

    #sudo ln -sf /usr/bin/python3.6 /usr/bin/python3
    #sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 2
    #sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.5 1
    #sudo update-alternatives --set python3 /usr/bin/python3.6

    echo "python3 version: " $(python3 -V)
   
    sudo python3 -m pip install --upgrade pip
    sudo python3 -m pip install --upgrade awscli boto3

    #wget $code_url_base/$code_ver
    #tar -xzf $code_ver
    #cd studio
    if [[ "{use_gpus}" -eq 1 ]]; then
        cudnn5="libcudnn5_5.1.10-1_cuda8.0_amd64.deb"
        cudnn6="libcudnn6_6.0.21-1_cuda8.0_amd64.deb"
        cuda_base="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1604/x86_64/"
        cuda_ver="cuda-repo-ubuntu1604_8.0.61-1_amd64.deb"

        # install cuda
        wget $cuda_base/$cuda_ver
        sudo dpkg -i $cuda_ver
        sudo apt -y update
        sudo apt install -y "cuda-8.0"

        # install cudnn
        wget $code_url_base/$cudnn5
        wget $code_url_base/$cudnn6
        sudo dpkg -i $cudnn5
        sudo dpkg -i $cudnn6

        sudo python  -m pip install tf-nightly tf-nightly-gpu --upgrade
        sudo python3 -m pip install tf-nightly tf-nightly-gpu --upgrade
    else
        sudo apt install -y default-jre
    fi
fi

if [[ "{use_gpus}" -ne 1 ]]; then
    rm -rf /usr/lib/x86_64-linux-gnu/libcuda*
fi

rm -rf studio
git clone $repo_url
if [[ $? -ne 0 ]]; then
    git clone https://github.com/studioml/studio
fi

cd studio
git pull
git checkout $branch
sudo python -m pip install -e . --upgrade
sudo python3 -m pip install -e . --upgrade



