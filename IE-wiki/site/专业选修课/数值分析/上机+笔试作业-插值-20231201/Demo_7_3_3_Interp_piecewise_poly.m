%
% �ֶ����Բ�ֵ�ͷֶ����� Hermite ��ֵ
%

clear; clc; 
close all;

f = @(x) 1./(1+x.^2); % �������ʽ
df = @(x) -(2*x)./(x.^2 + 1).^2; % һ�׵���, ����Hermite��ֵ
a = -5;  b = 5;  % ��ֵ����
n = 10;          % ����ȷ���
h = (b-a)/n;     % ���� 
xi = a : h : b;  % ��ֵ�ڵ�
fi = f(xi);      % ��ֵ�ڵ��ϵĺ���ֵ
dfi = df(xi);    % һ�׵���ֵ

x = a : (b-a)/500 : b; % ��Ҫ��ֵ�ĵ㣬���ڻ�ͼ

% �������Բ�ֵ����
L1 = @(x,x0,x1,f0,f1) f0*(x-x1)/(x0-x1) + f1*(x-x0)/(x1-x0);

% ������������Hermite��ֵ����
H3 = @(x,x0,x1,f0,f1,df0,df1) ...
   (f0*(1+2*(x-x0)/(x1-x0))+df0*(x-x0))*((x-x1)/(x0-x1))^2 + ...
   (f1*(1+2*(x-x1)/(x0-x1))+df1*(x-x1))*((x-x0)/(x1-x0))^2;

% �ֶβ�ֵ
N = length(x);
y1 = zeros(1,N);  % �ֶ����Բ�ֵ
y2 = zeros(1,N);  % �ֶ�����Hermite��ֵ
for j = 1 : N
   %    idx = find(xi>=x(j)); % Ѱ�� x(j) ���ڵ�С���� [x_k,x_{k+1}]
   %    k = idx(1)-1;
   %    if k==0
   %       k = k + 1;
   %    end
   for k=1:n+1   % Ѱ�� x(j) ���ڵ�С���� [x_k,x_{k+1}]
      if xi(k) >= x(j)
         break;  % �ҵ���һ����С�� x(j) �Ĳ�ֵ�ڵ�
      end
   end
   if k>1
      k=k-1;
   end
%    fprintf('x(j)=%.2f, k=%d, ��ֵС����: [%.2f,%.2f]\n', ...
%       x(j), k, xi(k),xi(k+1))
   y1(j) = L1(x(j),xi(k),xi(k+1),fi(k),fi(k+1));
   y2(j) = H3(x(j),xi(k),xi(k+1),fi(k),fi(k+1),dfi(k),dfi(k+1));
end

% ��ͼ
hold on;
plot(x,f(x),'r-', 'LineWidth',2);  % f(x) ͼ��
plot(x,y1,'b-', 'LineWidth',2,'markersize',5); % �ֶ����Բ�ֵͼ��
plot(x,y2,'k-', 'LineWidth',2,'markersize',10); % �ֶ�����Hermite��ֵͼ��
titstr=['n=',int2str(n)]; title(titstr,'fontsize',14);
axis([-5,5,-1,2]);

plot(xi,fi,'ok','markersize',10,'LineWidth',1.5); % ���Ʋ�ֵ�ڵ�
legend('f(x)','piecewise L1(x)','piecewise H3(x)','data');
set(gca,'FontSize',15);
hold off
