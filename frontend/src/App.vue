<template>
  <div id="app">
    <nav class="navbar">
      <div class="container">
        <router-link to="/" class="nav-brand">
          <div class="logo-icon">📊</div>
          <div class="brand-text">
            <h1>PolicyGraph QA</h1>
            <p>Intelligent Insurance Analysis</p>
          </div>
        </router-link>
        <div class="nav-links">
          <router-link to="/" class="nav-link">홈</router-link>
          <router-link to="/ingestion" class="nav-link">PDF 업로드</router-link>
          <router-link to="/query" class="nav-link highlight">질의하기</router-link>
        </div>
      </div>
    </nav>

    <main>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <footer class="footer">
      <div class="container">
        <div class="footer-content">
          <div class="footer-brand">
            <h3>PolicyGraph QA</h3>
            <p>Advanced RAG System for Insurance Policies</p>
          </div>
          <div class="footer-links">
            <p>&copy; 2025 <a href="https://www.uengine.io" target="_blank">uEngine</a>. All rights reserved.</p>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style scoped>
.navbar {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  position: sticky;
  top: 0;
  z-index: 100;
  height: 80px;
  display: flex;
  align-items: center;
}

.navbar .container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 1rem;
  text-decoration: none;
}

.logo-icon {
  font-size: 2rem;
  background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.brand-text h1 {
  font-size: 1.25rem;
  color: var(--text-color);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.brand-text p {
  font-size: 0.75rem;
  color: var(--text-light);
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.nav-links {
  display: flex;
  gap: 0.5rem;
}

.nav-link {
  text-decoration: none;
  color: var(--text-light);
  font-weight: 600;
  padding: 0.625rem 1.25rem;
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
  font-size: 0.9375rem;
}

.nav-link:hover {
  color: var(--primary-color);
  background: rgba(79, 70, 229, 0.05);
}

.nav-link.router-link-active {
  color: var(--primary-color);
  background: rgba(79, 70, 229, 0.08);
}

.nav-link.highlight {
  background: var(--primary-color);
  color: white;
  box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2);
}

.nav-link.highlight:hover {
  background: var(--secondary-color);
  transform: translateY(-1px);
  box-shadow: 0 6px 8px -1px rgba(79, 70, 229, 0.3);
}

main {
  flex: 1;
  background-color: #F8FAFC;
}

.footer {
  background: white;
  border-top: 1px solid var(--border-color);
  padding: 3rem 0;
  margin-top: auto;
}

.footer-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-brand h3 {
  font-size: 1.125rem;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.footer-brand p {
  color: var(--text-light);
  font-size: 0.875rem;
}

.footer-links {
  color: var(--text-light);
  font-size: 0.875rem;
}

.footer-links a {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 600;
  transition: color 0.2s ease;
}

.footer-links a:hover {
  color: var(--secondary-color);
  text-decoration: underline;
}

/* Page Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
