<script setup lang="ts">
import { useRoute } from 'vue-router'
import {
  LayoutDashboard,
  Mail,
  CheckCircle2,
  ListFilter,
  MessageSquare,
  Newspaper,
  Users,
  BarChart3,
  Settings,
  Shield,
  Sun,
  Moon,
} from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { useTheme } from '@/composables/useTheme'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarSeparator,
} from '@/components/ui/sidebar'

const route = useRoute()
const appStore = useAppStore()
const { isDark, toggleTheme } = useTheme()

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/emails', label: 'Emails', icon: Mail },
  { to: '/review', label: 'Review', icon: CheckCircle2, badge: true },
  { to: '/rules', label: 'Règles', icon: ListFilter },
  { to: '/newsletters', label: 'Newsletters', icon: Newspaper },
  { to: '/senders', label: 'Expéditeurs', icon: Users },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
]

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}
</script>

<template>
  <Sidebar collapsible="icon">
    <!-- Logo -->
    <SidebarHeader>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton as-child size="lg" class="data-[slot=sidebar-menu-button]:!p-1.5">
            <router-link to="/">
              <Shield class="!size-5 text-primary" />
              <span class="text-base font-semibold">InboxShield</span>
            </router-link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarHeader>

    <SidebarContent>
      <!-- Navigation principale -->
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem v-for="item in navItems" :key="item.to">
              <SidebarMenuButton
                as-child
                :is-active="isActive(item.to)"
                :tooltip="item.label"
              >
                <router-link :to="item.to">
                  <component :is="item.icon" />
                  <span>{{ item.label }}</span>
                </router-link>
              </SidebarMenuButton>
              <SidebarMenuBadge v-if="item.badge && appStore.reviewCount > 0">
                {{ appStore.reviewCount }}
              </SidebarMenuBadge>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>

      <!-- Navigation secondaire — poussée en bas -->
      <SidebarGroup class="mt-auto">
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarSeparator />
            <SidebarMenuItem>
              <SidebarMenuButton as-child :is-active="isActive('/settings')" tooltip="Paramètres">
                <router-link to="/settings">
                  <Settings />
                  <span>Paramètres</span>
                </router-link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton :tooltip="isDark ? 'Mode clair' : 'Mode sombre'" @click="toggleTheme">
                <Sun v-if="isDark" />
                <Moon v-else />
                <span>{{ isDark ? 'Mode clair' : 'Mode sombre' }}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>

    <SidebarRail />
  </Sidebar>
</template>
