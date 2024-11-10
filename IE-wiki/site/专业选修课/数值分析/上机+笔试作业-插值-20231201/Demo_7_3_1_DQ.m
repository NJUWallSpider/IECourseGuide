%
% ������� -- ������ʽ
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
% ����˵����
% ��������� x Ϊ�ڵ㣬y Ϊ����ֵ��ע�⣺���� x ������ y �ĳ��ȱ���һ�£�
% ���������
%    p �������в��̣������̱��е�����ֵ
%    q Ϊ���̱��жԽ��ߵ�ֵ

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