<template>
  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <strong style="color: var(--text)">云集商城</strong>
        <p style="margin: 8px 0 0; max-width: 380px; line-height: 1.7">
          演示电商站点，基于 Vue 3 + Django 5.2 + DRF 构建。支付能力为模拟支付，
          不发生任何真实资金交易。
        </p>
      </div>
      <div>
        <div style="margin-bottom: 8px; color: var(--text); font-weight: 600">帮助</div>
        <RouterLink to="/pages/help" style="display: block; margin-bottom: 6px">帮助中心</RouterLink>
        <RouterLink to="/pages/about" style="display: block">关于我们</RouterLink>
      </div>
      <div>
        <div style="margin-bottom: 8px; color: var(--text); font-weight: 600">演示账号</div>
        <div>普通用户：demo / ShopDemo2026</div>
        <div>运营账号：operator / ShopOperator2026</div>
        <div>管理员：admin / ShopAdmin2026</div>
      </div>
    </div>
  </footer>
</template>
