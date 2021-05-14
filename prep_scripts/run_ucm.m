% MATLAB script to get Ultrametric Contour Maps for images:
% Clone this github repo first:
% https://github.com/jponttuset/mcg/tree/master/pre-trained
%
% Author: Ankush Gupta

% path to the directory containing images, which need to be segmented
% img_dir = 'dir/containing/images';
img_dir = '../../depth_seg_images/2021-05-11';
% path to the mcg/pre-trained directory.
% mcg_dir = '/path/to/mcg/pre-trained';
% linux/ubuntu version
mcg_dir = '/code/tmp/mcg/pre-trained';
fprintf('assuming running on WSL/Linux platform \n')
fprintf('if not, switch to WSL/linux and run "matlab" command \n')

imsize = [240,NaN];
% "install" the MCG toolbox:
run(fullfile(mcg_dir,'install.m'));

% get the image names:
imname = dir(fullfile(img_dir,'*'));
imname = {imname.name};

% process:
names = cell(numel(imname),1);
ucms = cell(numel(imname),1);

%parpool('AGLocal',4);
parfor i = 1:numel(imname)
	fprintf('%d of %d\n',i,numel(imname));
	try
        im_name = fullfile(img_dir,imname{i});
		im = imread(im_name);
	catch
		fprintf('err\n');
		continue;
    end
    im = uint8(imresize(im,imsize));
	names{i} = imname{i};
	ucms{i} = im2ucm(im,'fast');
end
save('../../depth_seg_images/result/ucm.mat','ucms','names','-v7.3');