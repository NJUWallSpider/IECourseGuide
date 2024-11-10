%
% 计算差商 -- 函数形式
%

clear all;
close all;

x = [-2 -1 1 2];
y = [5 3 17 21];
[p, q] = DQ(x,y);
p


function [p, q] = DQ(x,y)
%
% Difference Quotient
%
% 参数说明：
% 输入参数： x 为节点，y 为函数值（注意：向量 x 与向量 y 的长度必须一致）
% 输出参数：
%    p 包含所有差商，即差商表中的所有值
%    q 为差商表中对角线的值

m = length(x);
x = x(:);
p = zeros(m, m+1);
p(:,1) = x; 
p(:,2) = y(:);
x(2:m)
x(1:m-1)
for k = 3 : m+1
    p(k-1:m, k) = diff(p(k-2:m, k-1)) ./ ( x(k-1:m) - x(1:m+2-k) );
end
q = diag(p(1:m,2:m+1));
end