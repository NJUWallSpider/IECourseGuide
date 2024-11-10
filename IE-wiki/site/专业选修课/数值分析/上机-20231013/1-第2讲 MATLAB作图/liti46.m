%理解meshgrid
% 使用向量 x 定义的 x 坐标和向量 y 定义的 y 坐标创建二维网格坐标。
x = 1:3;
y = 1:5;
[X,Y] = meshgrid(x,y)
X.^2+Y.^2

